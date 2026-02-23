"""
Database executor: query execution with pagination, projection,
timeout protection, result caps, and streaming support.
"""

from typing import Any, Dict, Generator, List, Optional, Tuple

from pymongo import MongoClient
from pymongo.errors import ExecutionTimeout

from logger import logger

# ---------------------- CONSTANTS ----------------------

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20
QUERY_TIMEOUT_MS = 5000
SERVER_SELECTION_TIMEOUT_MS = 5000


# ---------------------- HELPERS ----------------------

def _stringify_ids(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert ObjectId fields to strings so they are JSON-serialisable."""
    for doc in docs:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
    return docs


def _build_projection(fields: Optional[List[str]]) -> Optional[Dict[str, int]]:
    """Convert a list of field names into a MongoDB projection dict."""
    if not fields:
        return None
    return {f: 1 for f in fields}


def _safe_client(mongo_uri: str) -> MongoClient:
    """Create a MongoClient with timeout protection."""
    return MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
    )


# ---------------------- MAIN QUERY EXECUTOR ----------------------

def execute_query(
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    mongo_query: Dict[str, Any],
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    projection_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute a find or aggregate query with pagination, projection, and timeout.

    Returns a dict with:
    - ``data``: list of documents for the current page
    - ``total_count``: total matching documents (for find queries)
    - ``page``: current page number
    - ``page_size``: effective page size
    """

    # enforce hard caps
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    # If the IR specified a limit (e.g. "top 10"), respect it as an
    # upper-bound on total results returned across all pages.
    ir_limit = mongo_query.get("limit")
    if ir_limit is not None and ir_limit > 0:
        effective_limit = min(ir_limit, MAX_PAGE_SIZE)
        page_size = min(page_size, effective_limit)
    else:
        effective_limit = None

    skip = (page - 1) * page_size

    projection = _build_projection(projection_fields)

    client = _safe_client(mongo_uri)
    try:
        db = client[database_name]
        collection = db[collection_name]

        if mongo_query["type"] == "find":
            mongo_filter = mongo_query.get("filter", {})

            # total count for pagination metadata
            total_count = collection.count_documents(
                mongo_filter,
                maxTimeMS=QUERY_TIMEOUT_MS,
            )

            # If IR limit is set, cap total_count for frontend pagination
            if effective_limit is not None:
                total_count = min(total_count, effective_limit)

            cursor = collection.find(
                mongo_filter,
                projection,
                max_time_ms=QUERY_TIMEOUT_MS,
            )

            if mongo_query.get("sort"):
                cursor = cursor.sort([mongo_query["sort"]])

            cursor = cursor.skip(skip).limit(page_size)

            results = _stringify_ids(list(cursor))

            return {
                "data": results,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
            }

        elif mongo_query["type"] == "aggregate":
            pipeline = list(mongo_query.get("pipeline", []))

            # Aggregation: run with maxTimeMS
            results = list(
                collection.aggregate(pipeline, maxTimeMS=QUERY_TIMEOUT_MS)
            )
            results = _stringify_ids(results)

            return {
                "data": results,
                "total_count": len(results),
                "page": 1,
                "page_size": len(results),
            }

        else:
            return {
                "data": [],
                "total_count": 0,
                "page": page,
                "page_size": page_size,
            }

    except ExecutionTimeout:
        raise TimeoutError("Query timed out after exceeding the time limit.")
    finally:
        client.close()


# ---------------------- STREAMING EXECUTOR ----------------------

def stream_query(
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    mongo_query: Dict[str, Any],
    limit_cap: int = MAX_PAGE_SIZE,
    projection_fields: Optional[List[str]] = None,
) -> Generator[Dict[str, Any], None, None]:
    """Yield documents one by one without loading the entire cursor.

    Uses a server-side cursor with ``max_time_ms`` and ``limit`` cap.
    """

    limit_cap = min(max(1, limit_cap), MAX_PAGE_SIZE)
    projection = _build_projection(projection_fields)

    client = _safe_client(mongo_uri)
    try:
        db = client[database_name]
        collection = db[collection_name]

        if mongo_query["type"] == "find":
            mongo_filter = mongo_query.get("filter", {})

            cursor = collection.find(
                mongo_filter,
                projection,
                max_time_ms=QUERY_TIMEOUT_MS,
            )

            if mongo_query.get("sort"):
                cursor = cursor.sort([mongo_query["sort"]])

            cursor = cursor.limit(limit_cap)

            for doc in cursor:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                yield doc

        elif mongo_query["type"] == "aggregate":
            pipeline = list(mongo_query.get("pipeline", []))
            for doc in collection.aggregate(pipeline, maxTimeMS=QUERY_TIMEOUT_MS):
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                yield doc

    except ExecutionTimeout:
        raise TimeoutError("Streaming query timed out.")
    finally:
        client.close()