"""
IR-to-MongoDB query compiler.

**Type-aware**: when ``field_types`` is provided, the compiler dynamically
selects the right MongoDB operator based on the detected data type of each
field — no special NL keywords ("contains", "like") are required:

  - ``string`` + ``eq``          → case-insensitive anchored regex (``^…$``)
  - ``array_of_strings`` + ``eq``→ case-insensitive *partial* regex (un-anchored)
    so that "options is Order" matches elements like "Take charge and lead the Order"
  - ``int`` / ``float`` (numeric)→ exact numeric match (no regex)
  - ``contains`` (explicit)      → always un-anchored regex regardless of type

When ``field_types`` is ``None`` or the field is not present in the map,
the compiler falls back to the existing heuristic (regex for strings,
pass-through for numbers).
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from bson import ObjectId as _ObjectId
except ImportError:          # pymongo not installed in test env
    _ObjectId = None

# Pattern for a 24-character hex string (MongoDB ObjectId)
_OBJECTID_RE = re.compile(r'^[0-9a-fA-F]{24}$')

# Fields whose type is "date" need values converted to datetime
_DATE_TYPES = frozenset({"date"})

# Common date/time formats, tried in order
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ",   # ISO with ms and Z
    "%Y-%m-%dT%H:%M:%SZ",      # ISO with Z
    "%Y-%m-%dT%H:%M:%S.%f",    # ISO with ms
    "%Y-%m-%dT%H:%M:%S",       # ISO
    "%Y-%m-%d %H:%M:%S",       # space-separated
    "%Y-%m-%d",                 # date only
    "%m/%d/%Y",                 # US format
    "%d/%m/%Y",                 # EU format
    "%d-%m-%Y",                 # EU dash
    "%B %d, %Y",               # January 1, 2025
    "%b %d, %Y",               # Jan 1, 2025
    "%Y",                       # year only
]


def _parse_date_value(value: Any) -> Any:
    """Try to convert a string value to a datetime object.

    Returns a ``datetime`` on success or the original value unchanged.
    Handles ISO strings, common date formats, and year-only integers.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # Plausible 4-digit year → start of that year
        if 1000 <= value <= 9999:
            return datetime(int(value), 1, 1)
        return value
    if not isinstance(value, str):
        return value
    val = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return value


# Types that should use partial (un-anchored) regex for the "eq" operator
_PARTIAL_MATCH_TYPES = frozenset({
    "array_of_strings",
    "array_mixed",
})


def _case_insensitive_eq(value: Any) -> Any:
    """For string values, return a case-insensitive regex match.
    For non-strings, return the value as-is."""
    if isinstance(value, str):
        escaped = re.escape(value)
        return {"$regex": f"^{escaped}$", "$options": "i"}
    return value


def _case_insensitive_contains(value: Any) -> Any:
    """For string values, return a case-insensitive partial match.
    Works on both plain string fields and array-of-strings fields."""
    if isinstance(value, str):
        escaped = re.escape(value)
        return {"$regex": escaped, "$options": "i"}
    return value


def _build_id_filter(value: Any) -> Dict[str, Any]:
    """Build a filter for ``_id`` that tries every plausible type.

    MongoDB stores ``_id`` as string, int, or ObjectId depending on the
    collection.  Rather than guessing, we produce an ``$or`` filter that
    matches any of the candidate types so the query succeeds regardless of
    the actual storage type.
    """
    candidates: list = []

    # Always try value as-is (string)
    str_val = str(value)
    candidates.append({"_id": str_val})

    # Try numeric conversion (e.g. "10009999" → 10009999)
    try:
        int_val = int(str_val)
        candidates.append({"_id": int_val})
    except (ValueError, TypeError):
        pass

    try:
        float_val = float(str_val)
        if float_val != int(float_val) if str_val.replace('.', '', 1).lstrip('-').isdigit() else False:
            candidates.append({"_id": float_val})
    except (ValueError, TypeError):
        pass

    # Try ObjectId (requires 24-hex-char string)
    if _ObjectId is not None and isinstance(str_val, str) and _OBJECTID_RE.match(str_val):
        candidates.append({"_id": _ObjectId(str_val)})

    if len(candidates) == 1:
        return candidates[0]
    return {"$or": candidates}


def _build_eq_filter(
    field: str,
    value: Any,
    field_types: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    """Dynamically decide how to filter on ``eq`` based on field type.

    Priority:
    1. If the value is a **list** → exact array match (user provided a
       JSON array literal like ``["Pearl White","Crane Wilbur"]``).
    2. If field is ``_id`` → use multi-type ``$or`` to handle string /
       int / ObjectId storage transparently.
    3. If ``field_types`` tells us the field is an array-of-strings →
       partial match (user writes "options is Order" and means *contains*).
    4. Otherwise fall back to ``_case_insensitive_eq`` (anchored regex for
       strings, exact match for numbers).
    """
    # Exact array match — user explicitly provided a list value
    if isinstance(value, list):
        return {field: value}

    # Special handling for _id — try all plausible types
    if field == "_id":
        return _build_id_filter(value)

    ftype = (field_types or {}).get(field)

    if ftype in _PARTIAL_MATCH_TYPES:
        # user said "eq" but the field is an array of strings —
        # translate to partial match automatically
        return {field: _case_insensitive_contains(value)}

    # If value looks like an ObjectId hex string, match as ObjectId
    if (isinstance(value, str) and _OBJECTID_RE.match(value)
            and _ObjectId is not None):
        return {field: _ObjectId(value)}

    return {field: _case_insensitive_eq(value)}


def build_match_stage(
    conditions: List[Dict[str, Any]],
    field_types: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build a MongoDB filter/match document from IR conditions.

    ``field_types`` is an optional dict mapping field names to their
    detected types (from ``schema_utils``).  When provided the compiler
    automatically chooses the best MongoDB operator per field.
    """
    if not conditions:
        return {}

    and_conditions: List[Dict[str, Any]] = []

    for condition in conditions:
        field = condition["field"]
        operator = condition["operator"]
        value = condition["value"]

        # Auto-convert string dates to datetime when the field type is "date"
        ftype = (field_types or {}).get(field)
        if ftype in _DATE_TYPES and operator != "exists":
            if isinstance(value, list):
                value = [_parse_date_value(v) for v in value]
            else:
                value = _parse_date_value(value)

        if operator == "eq":
            # For date fields, eq means the whole day unless time is given
            if ftype in _DATE_TYPES and isinstance(value, datetime):
                # If it's midnight (date-only), match the whole day
                if value.hour == 0 and value.minute == 0 and value.second == 0:
                    day_start = value
                    day_end = value.replace(hour=23, minute=59, second=59, microsecond=999999)
                    and_conditions.append({field: {"$gte": day_start, "$lte": day_end}})
                else:
                    and_conditions.append({field: value})
            else:
                and_conditions.append(_build_eq_filter(field, value, field_types))
        elif operator == "contains":
            # If value looks like an ObjectId hex string, match as ObjectId
            if (isinstance(value, str) and _OBJECTID_RE.match(value)
                    and _ObjectId is not None):
                and_conditions.append({field: _ObjectId(value)})
            # Date fields: treat contains as eq (regex doesn't work on dates)
            elif ftype in _DATE_TYPES and isinstance(value, datetime):
                if value.hour == 0 and value.minute == 0 and value.second == 0:
                    day_start = value
                    day_end = value.replace(hour=23, minute=59, second=59, microsecond=999999)
                    and_conditions.append({field: {"$gte": day_start, "$lte": day_end}})
                else:
                    and_conditions.append({field: value})
            else:
                and_conditions.append({field: _case_insensitive_contains(value)})
        elif operator == "gt":
            and_conditions.append({field: {"$gt": value}})
        elif operator == "gte":
            and_conditions.append({field: {"$gte": value}})
        elif operator == "lt":
            and_conditions.append({field: {"$lt": value}})
        elif operator == "lte":
            and_conditions.append({field: {"$lte": value}})
        elif operator == "ne":
            and_conditions.append({field: {"$ne": value}})
        elif operator == "in":
            and_conditions.append({field: {"$in": value if isinstance(value, list) else [value]}})
        elif operator == "exists":
            and_conditions.append({field: {"$exists": bool(value)}})

    if len(and_conditions) == 1:
        return and_conditions[0]

    return {"$and": and_conditions}


def compile_ir_to_mongo(
    ir: Dict[str, Any],
    field_types: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Compile a validated IR into a MongoDB-ready query dict.

    ``field_types`` is forwarded to ``build_match_stage`` so that operator
    selection is type-aware.
    """

    if ir["operation"] == "find":

        mongo_filter = build_match_stage(ir["conditions"], field_types)

        mongo_query: Dict[str, Any] = {
            "type": "find",
            "filter": mongo_filter,
            "sort": None,
            "limit": ir.get("limit"),
        }

        if ir.get("sort"):
            direction = 1 if ir["sort"]["direction"] == "asc" else -1
            mongo_query["sort"] = (ir["sort"]["field"], direction)

        return mongo_query

    # -------- AGGREGATION --------
    elif ir["operation"] == "aggregate":

        match_stage = build_match_stage(ir["conditions"], field_types)

        pipeline: List[Dict[str, Any]] = []

        if match_stage:
            pipeline.append({"$match": match_stage})

        agg_type = ir["aggregation"]["type"]
        field = ir["aggregation"]["field"]

        if agg_type == "count":
            pipeline.append({"$count": "result"})
        else:
            operator_map = {
                "avg": "$avg",
                "sum": "$sum",
                "max": "$max",
                "min": "$min",
            }

            pipeline.append({
                "$group": {
                    "_id": None,
                    "result": {
                        operator_map[agg_type]: f"${field}"
                    }
                }
            })

        return {
            "type": "aggregate",
            "pipeline": pipeline,
        }

    return {"type": "find", "filter": {}, "sort": None, "limit": 20}