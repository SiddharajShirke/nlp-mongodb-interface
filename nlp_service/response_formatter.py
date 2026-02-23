"""
Response formatter: builds the final JSON response for the API.

Supports pagination metadata, index info, and large-dataset warnings.
"""

from typing import Any, Dict, List, Optional

LARGE_DATASET_THRESHOLD = 100_000


def paraphrase_ir(ir: Dict[str, Any]) -> str:
    """Generate a human-readable description of the parsed IR."""
    parts: List[str] = []

    if ir["operation"] == "find":
        parts.append("Showing records")
    elif ir["operation"] == "aggregate":
        agg_type = ir["aggregation"]["type"]
        if agg_type == "count":
            parts.append("Counting records")
        else:
            parts.append(f"Calculating {agg_type} of {ir['aggregation']['field']}")

    for condition in ir.get("conditions", []):
        field = condition["field"]
        operator = condition["operator"]
        value = condition["value"]

        op_map = {
            "eq": "is", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=", "ne": "!=",
            "in": "in", "exists": "exists",
        }
        parts.append(f"where {field} {op_map.get(operator, operator)} {value}")

    if ir.get("sort"):
        direction = ir["sort"]["direction"]
        field = ir["sort"]["field"]
        parts.append(f"sorted by {field} ({direction})")

    if ir.get("projection"):
        parts.append(f"showing fields: {', '.join(ir['projection'])}")

    if ir.get("limit"):
        parts.append(f"limited to {ir['limit']} results")

    return " ".join(parts) + "."


def clean_documents(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove ``_id`` and sanitise non-JSON-serialisable values (bytes,
    datetime, ObjectId, etc.) so FastAPI can encode the response."""
    cleaned = []
    for doc in results:
        doc.pop("_id", None)
        cleaned.append(_sanitise_value(doc))
    return cleaned


def _sanitise_value(obj: Any) -> Any:
    """Recursively convert non-JSON-safe types to safe representations."""
    if isinstance(obj, dict):
        return {k: _sanitise_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitise_value(item) for item in obj]
    if isinstance(obj, bytes):
        # Binary fields (e.g. vector embeddings) — try UTF-8, else base64
        try:
            return obj.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            import base64
            return f"[binary {len(obj)} bytes]"
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    # datetime, ObjectId, Decimal128, etc.
    return str(obj)


def format_response(
    ir: Dict[str, Any],
    query_result: Dict[str, Any],
    indexes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build the final response dict.

    Parameters
    ----------
    ir : dict
        The validated intermediate representation.
    query_result : dict
        Output from ``execute_query`` with keys: data, total_count, page, page_size.
    indexes : list[dict] | None
        Index information for the collection (optional).
    """

    interpretation = paraphrase_ir(ir)

    data = query_result.get("data", [])
    total_count = query_result.get("total_count", len(data))
    page = query_result.get("page", 1)
    page_size = query_result.get("page_size", len(data))

    # aggregation result — return both scalar `result` AND a `data` list
    # so the frontend table renderer works uniformly.
    if ir["operation"] == "aggregate":
        value = data[0].get("result", 0) if data else 0
        agg_data = clean_documents(data) if data else [{"result": value}]
        response: Dict[str, Any] = {
            "interpretation": interpretation,
            "interpreted_ir": ir,
            "result": value,
            "page": 1,
            "page_size": len(agg_data),
            "total_results": len(agg_data),
            "result_count": len(agg_data),
            "data": agg_data,
        }
        if indexes is not None:
            response["indexes"] = indexes
        return response

    # find result with pagination
    cleaned = clean_documents(data)

    response = {
        "interpretation": interpretation,
        "interpreted_ir": ir,
        "page": page,
        "page_size": page_size,
        "total_results": total_count,
        "result_count": len(cleaned),
        "data": cleaned,
    }

    if indexes is not None:
        response["indexes"] = indexes

    # add warning for very large datasets
    if total_count > LARGE_DATASET_THRESHOLD:
        response["warning"] = (
            "Large dataset detected. Consider refining query or using pagination."
        )

    return response
