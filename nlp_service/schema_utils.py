"""
Schema utilities: sampling, flattening, caching, and index inspection.

Provides **type-aware** schema detection — every field is classified into
one of these types so the query compiler can dynamically choose the right
MongoDB operator:

    string            — plain string
    int / float       — numeric
    bool              — boolean
    date              — datetime / timestamp
    array_of_strings  — list whose elements are strings
    array_of_numbers  — list whose elements are int/float
    array_of_objects  — list whose elements are dicts (expanded via dot-notation)
    array_mixed       — list with mixed element types
    object            — embedded document (expanded via dot-notation)
    unknown           — anything else (binary, null, ObjectId, …)
"""

import datetime as _dt
from typing import Any, Dict, List, Optional, Set, Tuple
from pymongo import MongoClient
from logger import logger


# ---------------------- TYPE NAMES ----------------------

TYPE_STRING = "string"
TYPE_INT = "int"
TYPE_FLOAT = "float"
TYPE_BOOL = "bool"
TYPE_ARRAY_STRINGS = "array_of_strings"
TYPE_ARRAY_NUMBERS = "array_of_numbers"
TYPE_ARRAY_OBJECTS = "array_of_objects"
TYPE_ARRAY_MIXED = "array_mixed"
TYPE_OBJECT = "object"
TYPE_DATE = "date"
TYPE_UNKNOWN = "unknown"


def _detect_type(value: Any) -> str:
    """Classify a single Python value into a schema type string."""
    if isinstance(value, bool):
        return TYPE_BOOL
    if isinstance(value, _dt.datetime):
        return TYPE_DATE
    if isinstance(value, _dt.date):
        return TYPE_DATE
    if isinstance(value, int):
        return TYPE_INT
    if isinstance(value, float):
        return TYPE_FLOAT
    if isinstance(value, str):
        return TYPE_STRING
    if isinstance(value, dict):
        return TYPE_OBJECT
    if isinstance(value, list):
        if not value:
            return TYPE_ARRAY_MIXED  # empty → unknown element type
        has_str = any(isinstance(v, str) for v in value)
        has_num = any(isinstance(v, (int, float)) for v in value)
        has_dict = any(isinstance(v, dict) for v in value)
        if has_dict:
            return TYPE_ARRAY_OBJECTS
        if has_str and not has_num:
            return TYPE_ARRAY_STRINGS
        if has_num and not has_str:
            return TYPE_ARRAY_NUMBERS
        return TYPE_ARRAY_MIXED
    return TYPE_UNKNOWN


# ---------------------- IN-MEMORY SCHEMA CACHE ----------------------

SchemaResult = Tuple[List[str], List[str], Dict[str, str]]
"""(allowed_fields, numeric_fields, field_types)"""

schema_cache: Dict[str, SchemaResult] = {}


def _cache_key(uri: str, db: str, collection: str) -> str:
    return f"{uri}-{db}-{collection}"


def clear_schema_cache() -> None:
    """Remove all cached schemas."""
    schema_cache.clear()


def invalidate_schema(uri: str, db: str, collection: str) -> None:
    """Remove a single collection from the cache."""
    key = _cache_key(uri, db, collection)
    schema_cache.pop(key, None)


# ---------------------- DOCUMENT FLATTENING ----------------------

def flatten_document(doc: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Recursively flatten a nested document into dot-notation keys.

    - Nested dicts are expanded (unlimited depth).
    - Arrays of **objects** are expanded: the first element's fields are
      used to discover nested paths (MongoDB natively supports dot-notation
      queries into arrays, e.g. ``options.type`` matches ``{options: [{type: "x"}]}``)
    - Arrays of primitives are treated as terminal fields.
    - ``_id`` is excluded.
    """
    items: Dict[str, Any] = {}
    for key, value in doc.items():
        if key == "_id" and parent_key == "":
            continue
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.update(flatten_document(value, new_key, sep))
        elif isinstance(value, list) and value:
            # Check if the array contains dicts (array of embedded documents)
            dict_elements = [el for el in value if isinstance(el, dict)]
            if dict_elements:
                # Flatten all dict elements to discover all possible fields
                for el in dict_elements:
                    items.update(flatten_document(el, new_key, sep))
            else:
                # Array of primitives — treat as terminal
                items[new_key] = value
        else:
            items[new_key] = value
    return items


# ---------------------- SCHEMA SAMPLING ----------------------

def get_collection_schema(
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    sample_size: int = 50,
) -> SchemaResult:
    """Sample *sample_size* documents and return
    ``(allowed_fields, numeric_fields, field_types)``.

    ``field_types`` maps every discovered field to its detected type
    (see module-level constants).  When a field has different types across
    sampled docs the *most specific* type wins (e.g. if one doc has
    ``options`` as ``array_of_strings`` and another has a plain ``string``,
    ``array_of_strings`` wins because it carries more information).

    For array-of-objects fields, the array is expanded into dot-notation
    sub-fields AND the parent ``field`` itself is recorded with type
    ``array_of_objects`` so the compiler can apply ``$elemMatch`` etc.
    """
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        db = client[database_name]
        collection = db[collection_name]

        cursor = collection.find().limit(sample_size)
        docs = list(cursor)
    finally:
        client.close()

    if not docs:
        return [], [], {}

    all_fields: Set[str] = set()
    numeric_fields: Set[str] = set()
    field_types: Dict[str, str] = {}

    # Priority for type merging — higher = more specific
    _type_priority = {
        TYPE_UNKNOWN: 0,
        TYPE_STRING: 1,
        TYPE_BOOL: 1,
        TYPE_DATE: 2,
        TYPE_INT: 2,
        TYPE_FLOAT: 2,
        TYPE_ARRAY_MIXED: 3,
        TYPE_ARRAY_NUMBERS: 4,
        TYPE_ARRAY_STRINGS: 4,
        TYPE_ARRAY_OBJECTS: 5,
        TYPE_OBJECT: 5,
    }

    for doc in docs:
        # Detect raw (pre-flatten) types for top-level and nested fields
        _detect_field_types_recursive(doc, "", field_types, _type_priority)

        # Flatten for field discovery
        flat = flatten_document(doc)
        for field, value in flat.items():
            all_fields.add(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric_fields.add(field)
            # Also track types for flattened sub-fields
            ftype = _detect_type(value)
            existing = field_types.get(field)
            if existing is None or _type_priority.get(ftype, 0) > _type_priority.get(existing, 0):
                field_types[field] = ftype

    sorted_fields = sorted(all_fields)
    sorted_numeric = sorted(numeric_fields)

    logger.info(
        "Schema sampled %d docs from %s.%s — %d fields (%d numeric), types: %s",
        len(docs), database_name, collection_name,
        len(sorted_fields), len(sorted_numeric), field_types,
    )
    return sorted_fields, sorted_numeric, field_types


def _detect_field_types_recursive(
    doc: Dict[str, Any],
    parent_key: str,
    field_types: Dict[str, str],
    priority: Dict[str, int],
    sep: str = ".",
) -> None:
    """Walk a document recursively and record the type of every field.

    This handles nested dicts and arrays so that *parent* array fields
    (e.g. ``options``) are correctly tagged as ``array_of_strings`` even
    though ``flatten_document`` doesn't keep the parent key.
    """
    for key, value in doc.items():
        if key == "_id" and parent_key == "":
            continue
        full_key = f"{parent_key}{sep}{key}" if parent_key else key
        ftype = _detect_type(value)
        existing = field_types.get(full_key)
        if existing is None or priority.get(ftype, 0) > priority.get(existing, 0):
            field_types[full_key] = ftype
        # Recurse into nested dicts
        if isinstance(value, dict):
            _detect_field_types_recursive(value, full_key, field_types, priority, sep)
        # Recurse into array elements that are dicts
        elif isinstance(value, list):
            for el in value:
                if isinstance(el, dict):
                    _detect_field_types_recursive(el, full_key, field_types, priority, sep)


# ---------------------- CACHED SCHEMA ACCESS ----------------------

def get_cached_schema(
    uri: str,
    db: str,
    collection: str,
    sample_size: int = 50,
) -> SchemaResult:
    """Return schema from cache if available, otherwise sample and cache.

    Returns ``(allowed_fields, numeric_fields, field_types)``.
    """
    key = _cache_key(uri, db, collection)

    if key in schema_cache:
        logger.info("Schema cache HIT for %s.%s", db, collection)
        return schema_cache[key]

    logger.info("Schema cache MISS for %s.%s — sampling…", db, collection)
    result = get_collection_schema(uri, db, collection, sample_size)
    schema_cache[key] = result
    return result


# ---------------------- INDEX INSPECTION ----------------------

def get_collection_indexes(
    mongo_uri: str,
    database_name: str,
    collection_name: str,
) -> List[Dict[str, Any]]:
    """Return a list of index descriptions for the collection.

    Each entry contains:
    - ``name``: index name
    - ``keys``: list of ``(field, direction)`` pairs
    - ``unique``: whether the index enforces uniqueness
    """
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        db = client[database_name]
        collection = db[collection_name]

        raw_indexes = collection.index_information()
    finally:
        client.close()

    indexes: List[Dict[str, Any]] = []
    for name, info in raw_indexes.items():
        indexes.append({
            "name": name,
            "keys": info.get("key", []),
            "unique": info.get("unique", False),
        })

    return indexes


def get_indexed_fields(indexes: List[Dict[str, Any]]) -> Set[str]:
    """Extract the set of indexed field names from index descriptions."""
    fields: Set[str] = set()
    for idx in indexes:
        for key_pair in idx.get("keys", []):
            if isinstance(key_pair, (list, tuple)) and len(key_pair) >= 1:
                fields.add(str(key_pair[0]))
            elif isinstance(key_pair, str):
                fields.add(key_pair)
    return fields
