"""
FastAPI NLP service — production-grade Natural Language Interface for MongoDB.

Features:
- Schema sampling (N documents) with nested field flattening
- In-memory schema caching per collection
- Pagination with hard caps
- Projection support
- Query timeout protection
- Index inspection and unindexed-field warnings
- Streaming response endpoint
- Full dot-notation nested field support
"""

import copy
import json
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from parser import parse_to_ir
from llm_parser import parse_with_llm
from ir_validator import validate_ir, resolve_field_name
from ir_compiler import compile_ir_to_mongo
from config import PARSER_MODE
from cluster_manager import list_databases, list_collections
from db_executor import execute_query, stream_query, MAX_PAGE_SIZE, DEFAULT_PAGE_SIZE
from schema_utils import (
    get_cached_schema,
    get_collection_indexes,
    get_indexed_fields,
    clear_schema_cache,
    invalidate_schema,
)
from response_formatter import format_response, _sanitise_value
from activity_tracker import (
    log_activity,
    get_commit_timeline,
    get_activity_stats,
    get_diagnosis_monthly,
    ACTIVITY_QUERY,
    ACTIVITY_DIAGNOSE,
    ACTIVITY_COMMIT,
)
from logger import logger


app = FastAPI(title="NLP MongoDB Interface", version="2.0.0")

# Clear schema cache on startup/reload so type changes are picked up
clear_schema_cache()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------- REQUEST MODELS ----------------------


class ClusterRequest(BaseModel):
    mongo_uri: str


class CollectionRequest(BaseModel):
    mongo_uri: str
    database_name: str


class NLPRequest(BaseModel):
    mongo_uri: str
    database_name: str
    collection_name: str
    query: str
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Results per page (max {MAX_PAGE_SIZE})",
    )
    history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Conversation history as [{role, content}, ...]",
    )
    user_email: Optional[str] = Field(
        default="anonymous",
        description="Email of the logged-in user (for activity tracking)",
    )


class SchemaRequest(BaseModel):
    mongo_uri: str
    database_name: str
    collection_name: str


class MutationRequest(BaseModel):
    """Request model for CRUD mutation operations (insert/update/delete)."""
    mongo_uri: str
    database_name: str
    collection_name: str
    query: str
    history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Conversation history as [{role, content}, ...]",
    )
    user_email: Optional[str] = Field(
        default="anonymous",
        description="Email of the logged-in user (for activity tracking)",
    )


class CommitRequest(BaseModel):
    """Request model for committing a previewed mutation."""
    mongo_uri: str
    database_name: str
    collection_name: str
    mutation: Dict[str, Any] = Field(
        description="The mutation plan returned by /mutation-preview",
    )
    user_email: Optional[str] = Field(
        default="anonymous",
        description="Email of the logged-in user (for activity tracking)",
    )


# ---------------------- ENDPOINTS ----------------------


@app.post("/connect-cluster")
def connect_cluster(request: ClusterRequest):
    try:
        return list_databases(request.mongo_uri)
    except Exception as e:
        logger.error("connect-cluster error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/get-collections")
def get_collections(request: CollectionRequest):
    try:
        collections = list_collections(
            request.mongo_uri,
            request.database_name,
        )
        return {"collections": collections}
    except Exception as e:
        logger.error("get-collections error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/get-schema")
def get_schema(request: SchemaRequest):
    """Return the sampled & flattened schema for a collection."""
    try:
        allowed_fields, numeric_fields, field_types = get_cached_schema(
            request.mongo_uri,
            request.database_name,
            request.collection_name,
        )
        return {
            "fields": allowed_fields,
            "numeric_fields": numeric_fields,
            "field_types": field_types,
            "total_fields": len(allowed_fields),
        }
    except Exception as e:
        logger.error("get-schema error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/get-indexes")
def get_indexes(request: SchemaRequest):
    """Return index information for a collection."""
    try:
        indexes = get_collection_indexes(
            request.mongo_uri,
            request.database_name,
            request.collection_name,
        )
        return {"indexes": indexes}
    except Exception as e:
        logger.error("get-indexes error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/clear-cache")
def clear_cache():
    """Clear the in-memory schema cache."""
    clear_schema_cache()
    return {"status": "cache cleared"}


@app.post("/run-nlp")
def run_nlp(request: NLPRequest):
    """Full NLP pipeline: schema → parse → validate → compile → execute → respond."""

    # 1. Schema sampling (cached)
    try:
        allowed_fields, numeric_fields, field_types = get_cached_schema(
            request.mongo_uri,
            request.database_name,
            request.collection_name,
        )
    except Exception as e:
        logger.error("Schema detection failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Schema detection failed: {e}")

    if not allowed_fields:
        raise HTTPException(status_code=400, detail="Collection empty or invalid")

    logger.info(
        "[PIPELINE] Step 1 — Schema: %d fields (%d numeric). Fields: %s  Types: %s",
        len(allowed_fields), len(numeric_fields), allowed_fields, field_types,
    )

    # 2. Parse NL query → IR (LLM primary, rule-based fallback)
    ir = None
    parser_used = "none"

    if PARSER_MODE in ("auto", "llm"):
        try:
            ir = parse_with_llm(
                request.query, allowed_fields, numeric_fields, field_types,
                history=request.history,
            )
            if ir:
                parser_used = "llm"
        except Exception as e:
            logger.warning("[PIPELINE] LLM parser error: %s — falling back", e)

    if not ir and PARSER_MODE in ("auto", "rule"):
        ir = parse_to_ir(request.query, allowed_fields, numeric_fields)
        if ir:
            parser_used = "rule-based"

    if not ir:
        raise HTTPException(
            status_code=400,
            detail="Could not understand the query. Try rephrasing.",
        )

    logger.info(
        "[PIPELINE] Step 2 — Parsed IR (parser=%s): operation=%s, conditions=%s, "
        "aggregation=%s, sort=%s, limit=%s, projection=%s",
        parser_used,
        ir.get("operation"), ir.get("conditions"), ir.get("aggregation"),
        ir.get("sort"), ir.get("limit"), ir.get("projection"),
    )

    # 3. Validate IR against full schema
    try:
        validated_ir = validate_ir(ir, allowed_fields)
    except ValueError as e:
        logger.warning("[PIPELINE] Step 3 — Validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    logger.info("[PIPELINE] Step 3 — Validation passed")

    # 4. Compile IR → MongoDB query (type-aware)
    mongo_query = compile_ir_to_mongo(validated_ir, field_types=field_types)

    logger.info(
        "[PIPELINE] Step 4 — Compiled Mongo query: type=%s, filter=%s, sort=%s, limit=%s",
        mongo_query.get("type"), mongo_query.get("filter"),
        mongo_query.get("sort"), mongo_query.get("limit"),
    )

    # (debug prints removed — use /diagnose endpoint instead)

    # 5. Extract projection from IR
    projection_fields = validated_ir.get("projection")

    # 6. Index inspection (never blocks execution)
    try:
        indexes = get_collection_indexes(
            request.mongo_uri,
            request.database_name,
            request.collection_name,
        )
    except Exception:
        indexes = []

    # 7. Execute with pagination, projection, timeout
    try:
        query_result = execute_query(
            request.mongo_uri,
            request.database_name,
            request.collection_name,
            mongo_query,
            page=request.page,
            page_size=request.page_size,
            projection_fields=projection_fields,
        )
    except TimeoutError:
        raise HTTPException(
            status_code=408,
            detail="Query timed out. Try a more specific query.",
        )
    except Exception as e:
        logger.error("[PIPELINE] Step 7 — Query execution failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Query execution error: {e}")

    logger.info(
        "[PIPELINE] Step 7 — Execution done: %d results on page %d (total %d)",
        len(query_result.get("data", [])),
        query_result.get("page", 1),
        query_result.get("total_count", 0),
    )

    # 8. Build response with optional index warning (NEVER blocks results)
    indexed_fields = get_indexed_fields(indexes)
    queried_fields = {c["field"] for c in validated_ir.get("conditions", [])}
    unindexed = queried_fields - indexed_fields - {"_id"}

    response = format_response(validated_ir, query_result, indexes)

    # Tag which parser produced the IR
    response["parser_used"] = parser_used

    # If 0 results, provide a sample of actual values for queried fields
    if query_result.get("total_count", 0) == 0 and validated_ir.get("conditions"):
        try:
            from pymongo import MongoClient as _MC
            _cl = _MC(request.mongo_uri, serverSelectionTimeoutMS=5000)
            try:
                _db = _cl[request.database_name]
                _co = _db[request.collection_name]
                value_hints = {}
                for cond in validated_ir["conditions"]:
                    fld = cond["field"]
                    # Sample up to 5 distinct values for the field
                    try:
                        distinct_vals = _co.distinct(fld)
                        # Flatten arrays-of-arrays into individual values
                        flat_vals = []
                        for v in distinct_vals:
                            if isinstance(v, list):
                                flat_vals.extend(str(x) for x in v[:5])
                            else:
                                flat_vals.append(str(v))
                        unique = list(dict.fromkeys(flat_vals))[:10]
                        value_hints[fld] = unique
                    except Exception:
                        pass
                if value_hints:
                    hint_str = "; ".join(
                        f"{fld}: {vals}" for fld, vals in value_hints.items()
                    )
                    response["value_hint"] = (
                        f"No match found. Actual values in your data — {hint_str}"
                    )
            finally:
                _cl.close()
        except Exception:
            pass

    if unindexed:
        existing_warning = response.get("warning", "")
        index_warning = (
            f"Queried field(s) not indexed: {', '.join(sorted(unindexed))}. "
            "Query executed successfully but may be slow on large collections. "
            "Consider adding indexes for better performance."
        )
        response["warning"] = (
            f"{existing_warning} {index_warning}".strip()
            if existing_warning
            else index_warning
        )
        logger.info("[PIPELINE] Step 8 — Index warning (non-blocking): %s", index_warning)

    # 9. Log activity (fire-and-forget)
    try:
        log_activity(
            request.mongo_uri, request.database_name,
            activity_type=ACTIVITY_QUERY,
            collection_name=request.collection_name,
            user_email=getattr(request, "user_email", "anonymous") or "anonymous",
            query=request.query,
            details={
                "parser": parser_used,
                "total_results": query_result.get("total_count", 0),
                "operation": validated_ir.get("operation"),
            },
        )
    except Exception:
        pass

    return response


@app.post("/run-nlp-stream")
def run_nlp_stream(request: NLPRequest):
    """Streaming NLP endpoint — yields JSON lines one document at a time."""

    # Schema
    try:
        allowed_fields, numeric_fields, field_types = get_cached_schema(
            request.mongo_uri,
            request.database_name,
            request.collection_name,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Schema detection failed: {e}")

    if not allowed_fields:
        raise HTTPException(status_code=400, detail="Collection empty or invalid")

    # Parse → Validate → Compile  (LLM primary, rule-based fallback)
    ir = None
    if PARSER_MODE in ("auto", "llm"):
        try:
            ir = parse_with_llm(
                request.query, allowed_fields, numeric_fields, field_types,
            )
        except Exception:
            pass
    if not ir and PARSER_MODE in ("auto", "rule"):
        ir = parse_to_ir(request.query, allowed_fields, numeric_fields)
    if not ir:
        raise HTTPException(
            status_code=400,
            detail="Could not understand the query. Try rephrasing.",
        )

    try:
        validated_ir = validate_ir(ir, allowed_fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    mongo_query = compile_ir_to_mongo(validated_ir, field_types=field_types)
    projection_fields = validated_ir.get("projection")

    limit_cap = min(request.page_size, MAX_PAGE_SIZE)

    def _generate():
        try:
            for doc in stream_query(
                request.mongo_uri,
                request.database_name,
                request.collection_name,
                mongo_query,
                limit_cap=limit_cap,
                projection_fields=projection_fields,
            ):
                doc.pop("_id", None)
                yield json.dumps(doc) + "\n"
        except TimeoutError:
            yield json.dumps({"error": "Stream timed out"}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(_generate(), media_type="application/x-ndjson")


@app.post("/diagnose-schema")
def diagnose_schema(request: NLPRequest):
    """Inspect raw schema flattening — shows exactly what fields the
    system discovered and whether array-of-objects expansion is working.

    Useful when fields like ``options.type`` are missing from the schema.
    Clears the cache for this collection first to force a fresh sample.
    """
    from schema_utils import get_collection_schema, flatten_document, schema_cache, _cache_key
    from pymongo import MongoClient

    # Force fresh sample
    key = _cache_key(request.mongo_uri, request.database_name, request.collection_name)
    schema_cache.pop(key, None)

    # Get one sample document for raw inspection
    client = MongoClient(request.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        db = client[request.database_name]
        coll = db[request.collection_name]
        sample_doc = coll.find_one()
    finally:
        client.close()

    raw_doc_preview = None
    flat_preview = None
    if sample_doc:
        if "_id" in sample_doc:
            sample_doc["_id"] = str(sample_doc["_id"])
        raw_doc_preview = {k: str(type(v).__name__) + ": " + repr(v)[:200] for k, v in sample_doc.items()}
        flat = flatten_document(sample_doc)
        flat_preview = {k: str(type(v).__name__) for k, v in flat.items()}

    # Now do full schema sampling
    allowed_fields, numeric_fields, field_types = get_collection_schema(
        request.mongo_uri, request.database_name, request.collection_name,
    )

    return {
        "sample_doc_types": raw_doc_preview,
        "flattened_fields": flat_preview,
        "allowed_fields": allowed_fields,
        "numeric_fields": numeric_fields,
        "field_types": field_types,
        "field_count": len(allowed_fields),
    }


@app.post("/diagnose")
def diagnose(request: NLPRequest):
    """Diagnostic endpoint — runs the full pipeline but returns every
    intermediate step instead of final results.  Use this to debug issues
    with field resolution, parsing, compilation, or query execution.

    Returns:
    - ``schema``: allowed_fields and numeric_fields from the cache/sample
    - ``parse``: raw IR from the parser (before validation)
    - ``resolve``: per-field resolution trace (raw → resolved)
    - ``validate``: validated IR (after field resolution)
    - ``compile``: compiled MongoDB query (filter, sort, limit, pipeline)
    - ``execute_preview``: first 3 documents from execution (or error)
    - ``index_info``: indexes and unindexed queried fields
    """
    trace: Dict[str, Any] = {"query": request.query, "steps": {}}

    # Step 0 — Raw sample document (shows actual data structure)
    try:
        from pymongo import MongoClient
        _client = MongoClient(request.mongo_uri, serverSelectionTimeoutMS=5000)
        try:
            _db = _client[request.database_name]
            _coll = _db[request.collection_name]
            _total_docs = _coll.count_documents({})
            _sample = _coll.find_one()
            if _sample:
                if "_id" in _sample:
                    _sample["_id"] = str(_sample["_id"])
                # Show type + truncated value for each field
                _raw_fields: Dict[str, Any] = {}
                for k, v in _sample.items():
                    vtype = type(v).__name__
                    if isinstance(v, list):
                        preview = f"[{len(v)} items] "
                        if v:
                            preview += repr(v[0])[:150]
                            if isinstance(v[0], dict):
                                preview = f"[{len(v)} objects] keys={list(v[0].keys())}"
                        _raw_fields[k] = f"({vtype}) {preview}"
                    elif isinstance(v, dict):
                        _raw_fields[k] = f"({vtype}) keys={list(v.keys())}"
                    else:
                        _raw_fields[k] = f"({vtype}) {repr(v)[:200]}"
            else:
                _raw_fields = None
            trace["steps"]["0_raw_sample"] = {
                "total_documents": _total_docs,
                "sample_fields": _raw_fields,
            }
        finally:
            _client.close()
    except Exception as e:
        trace["steps"]["0_raw_sample"] = {"error": str(e)}

    # Step 1 — Schema (with type detection)
    try:
        allowed_fields, numeric_fields, field_types = get_cached_schema(
            request.mongo_uri, request.database_name, request.collection_name,
        )
        trace["steps"]["1_schema"] = {
            "status": "ok",
            "allowed_fields": allowed_fields,
            "numeric_fields": numeric_fields,
            "field_types": field_types,
            "field_count": len(allowed_fields),
        }
    except Exception as e:
        trace["steps"]["1_schema"] = {"status": "error", "error": str(e)}
        return trace

    # Step 2 — Parse (LLM primary, rule-based fallback)
    ir = None
    parser_used = "none"
    if PARSER_MODE in ("auto", "llm"):
        try:
            ir = parse_with_llm(
                request.query, allowed_fields, numeric_fields,
                trace["steps"]["1_schema"].get("field_types"),
                history=request.history,
            )
            if ir:
                parser_used = "llm"
        except Exception as e:
            logger.warning("[DIAGNOSE] LLM parser error: %s", e)
    if not ir and PARSER_MODE in ("auto", "rule"):
        ir = parse_to_ir(request.query, allowed_fields, numeric_fields)
        if ir:
            parser_used = "rule-based"
    if not ir:
        trace["steps"]["2_parse"] = {
            "status": "error",
            "error": "Could not understand the query",
        }
        return trace
    # deep copy so we preserve the raw IR before validation mutates it
    raw_ir = copy.deepcopy(ir)
    trace["steps"]["2_parse"] = {
        "status": "ok",
        "parser": parser_used,
        "raw_ir": raw_ir,
    }

    # Step 3 — Field resolution trace
    resolution_trace = []
    for cond in ir.get("conditions", []):
        raw = cond["field"]
        resolved = resolve_field_name(raw, allowed_fields)
        resolution_trace.append({
            "raw_field": raw,
            "resolved_field": resolved,
            "matched": resolved is not None,
        })
    agg = ir.get("aggregation")
    if agg and agg.get("field"):
        raw = agg["field"]
        resolved = resolve_field_name(raw, allowed_fields)
        resolution_trace.append({
            "raw_field": raw, "resolved_field": resolved,
            "context": "aggregation", "matched": resolved is not None,
        })
    sort = ir.get("sort")
    if sort and sort.get("field"):
        raw = sort["field"]
        resolved = resolve_field_name(raw, allowed_fields)
        resolution_trace.append({
            "raw_field": raw, "resolved_field": resolved,
            "context": "sort", "matched": resolved is not None,
        })
    for pf in ir.get("projection", []) or []:
        resolved = resolve_field_name(pf, allowed_fields)
        resolution_trace.append({
            "raw_field": pf, "resolved_field": resolved,
            "context": "projection", "matched": resolved is not None,
        })
    trace["steps"]["3_resolve"] = resolution_trace

    # Step 4 — Validate
    try:
        validated_ir = validate_ir(ir, allowed_fields)
        trace["steps"]["4_validate"] = {"status": "ok", "validated_ir": validated_ir}
    except ValueError as e:
        trace["steps"]["4_validate"] = {"status": "error", "error": str(e)}
        return trace

    # Step 5 — Compile (type-aware)
    mongo_query = compile_ir_to_mongo(validated_ir, field_types=field_types)
    # Convert filter/pipeline to JSON-safe string for readability
    trace["steps"]["5_compile"] = {
        "status": "ok",
        "type": mongo_query.get("type"),
        "filter": str(mongo_query.get("filter")),
        "sort": str(mongo_query.get("sort")),
        "limit": mongo_query.get("limit"),
        "pipeline": str(mongo_query.get("pipeline")) if mongo_query.get("pipeline") else None,
    }

    # Step 6 — Execute preview (first 3 docs)
    try:
        query_result = execute_query(
            request.mongo_uri, request.database_name, request.collection_name,
            mongo_query, page=1, page_size=3,
            projection_fields=validated_ir.get("projection"),
        )
        trace["steps"]["6_execute_preview"] = {
            "status": "ok",
            "total_count": query_result.get("total_count", 0),
            "returned": len(query_result.get("data", [])),
            "sample_docs": query_result.get("data", [])[:3],
        }
    except Exception as e:
        trace["steps"]["6_execute_preview"] = {"status": "error", "error": str(e)}

    # Step 7 — Index info
    try:
        indexes = get_collection_indexes(
            request.mongo_uri, request.database_name, request.collection_name,
        )
        indexed_fields = get_indexed_fields(indexes)
        queried_fields = {c["field"] for c in validated_ir.get("conditions", [])}
        unindexed = queried_fields - indexed_fields - {"_id"}
        trace["steps"]["7_index_info"] = {
            "indexes": [idx["name"] for idx in indexes],
            "indexed_fields": sorted(indexed_fields),
            "queried_fields": sorted(queried_fields),
            "unindexed_fields": sorted(unindexed),
        }
    except Exception as e:
        trace["steps"]["7_index_info"] = {"error": str(e)}

    # Sanitise the entire trace so BSON types (Decimal128, datetime,
    # ObjectId, bytes, etc.) are JSON-serialisable.
    sanitised = _sanitise_value(trace)

    # Log diagnosis activity (fire-and-forget)
    try:
        exec_step = trace.get("steps", {}).get("6_execute_preview", {})
        severity = "ok"
        for step_key in ("1_schema", "2_parse", "4_validate", "6_execute_preview"):
            st = trace.get("steps", {}).get(step_key, {})
            if isinstance(st, dict) and st.get("status") == "error":
                severity = "error"
                break
            if isinstance(st, dict) and st.get("error"):
                severity = "warning"
        log_activity(
            request.mongo_uri, request.database_name,
            activity_type=ACTIVITY_DIAGNOSE,
            collection_name=request.collection_name,
            user_email=getattr(request, "user_email", "anonymous") or "anonymous",
            query=request.query,
            details={
                "severity": severity,
                "total_results": exec_step.get("total_count", 0) if isinstance(exec_step, dict) else 0,
                "parser": trace.get("steps", {}).get("2_parse", {}).get("parser", "unknown"),
            },
        )
    except Exception:
        pass

    return sanitised


# ====================== MONGO EDIT — CRUD MUTATIONS ======================


def _build_mutation_prompt(
    query: str,
    allowed_fields: List[str],
    numeric_fields: List[str],
    field_types: Optional[Dict[str, str]],
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Build a dynamic, schema-aware prompt for LLM mutation planning.

    The prompt is constructed entirely from the REAL collection schema — no
    hard-coded field names or collection-specific examples.  This makes it
    work for ANY MongoDB database/collection the user connects to.
    """
    from llm_parser import _build_schema_block

    schema_block = _build_schema_block(allowed_fields, numeric_fields, field_types)

    # Build a concise list of existing field names for the LLM to reference
    field_list = ", ".join(allowed_fields[:60])  # cap to keep prompt short

    # Pick a sample field + _id for inline guidance (if available)
    sample_field = next(
        (f for f in allowed_fields if f not in ("_id",)), "status"
    )

    history_block = ""
    if history and len(history) > 0:
        recent = history[-10:]
        lines = []
        for msg in recent:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            if len(content) > 300:
                content = content[:300] + "..."
            lines.append(f"  {role}: {content}")
        history_block = (
            "\n\nCONVERSATION HISTORY:\n" + "\n".join(lines)
        )

    return f"""You are a MongoDB mutation planner.  Given a user's natural-language
request and the collection schema, output a single JSON object representing
the MongoDB operation to perform.

DATABASE SCHEMA (field → type):
{schema_block}

Existing fields: [{field_list}]

OUTPUT FORMAT — respond with ONLY a raw JSON object (no markdown fences, no
explanation, no extra text):
{{
  "operation": "insert" | "update" | "delete",
  "description": "<one-line human-readable summary>",
  "filter": {{ ... }} | null,
  "update": {{ "$set"|"$unset"|"$inc"|"$push"|... : {{ ... }} }} | null,
  "document": {{ ... }} | null,
  "documents": [ {{ ... }} ] | null,
  "multi": true | false,
  "estimated_affected": null
}}

RULES (apply dynamically to ANY collection):
1. INSERT: set "document" (or "documents" for bulk). filter/update = null.
2. UPDATE: set "filter" + "update". ALWAYS wrap values in a MongoDB update
   operator ($set, $unset, $inc, $push, $pull, $rename, etc.).
   NEVER put bare field:value directly in "update".
3. DELETE: set "filter". document/update = null.
4. For EXISTING fields, match the schema name exactly (case-sensitive, dot-notation).
   For NEW fields the user wants to add, use the name they specify.
5. Distinguish intent carefully:
   • "add/set/change field X on document Y" → UPDATE with $set
   • "remove/drop field X from document Y" → UPDATE with $unset
   • "add/create/insert a new document/record/entry" → INSERT
   • "delete/remove document/record/row matching …" → DELETE
   • "increase/decrement field X by N" → UPDATE with $inc
6. _id handling: always pass the _id value the user gives as a STRING.
   Example: {{"_id": "10009999"}} — never cast to int or ObjectId yourself.
7. "multi" = true ONLY when the user says "all", "every", "many", "bulk",
   or the filter clearly matches multiple documents.  Default false.
8. "estimated_affected" should always be null (the server calculates it).
9. Values: keep number literals as numbers, strings as strings, booleans as
   booleans.  Infer type from context (e.g. "price 100" → 100 as number).
10. "description" must clearly state what will happen.

USER QUERY: "{query}"
{history_block}
Respond with ONLY the JSON object."""


def _call_mutation_groq(
    prompt: str,
    models_to_try: List[str],
) -> Optional[str]:
    """Call Groq API for mutation parsing. Returns raw text or None."""
    import time as _time
    from llm_parser import _get_groq_client

    client = _get_groq_client()
    if client is None:
        raise RuntimeError(
            "Could not initialise the Groq AI client. Ensure the "
            "groq SDK is installed (pip install groq) and "
            "your GROQ_API_KEY is valid."
        )

    raw_text = None
    for model_name in models_to_try:
        logger.info("[MUTATION-LLM] Trying Groq model %s", model_name)
        max_retries = 1
        model_succeeded = False

        for attempt in range(max_retries + 1):
            start = _time.time()
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=2048,
                )
                elapsed = _time.time() - start
                raw_text = response.choices[0].message.content
                logger.info("[MUTATION-LLM] Groq %s responded in %.2fs (%d chars)",
                            model_name, elapsed, len(raw_text))
                model_succeeded = True
                break
            except Exception as e:
                elapsed = _time.time() - start
                err_str = str(e)
                is_retriable = "429" in err_str or "404" in err_str
                if is_retriable:
                    if "429" in err_str and attempt < max_retries:
                        wait = min(5, 4 * (attempt + 1))
                        logger.warning("[MUTATION-LLM] Groq %s rate-limited, retrying in %ds...",
                                       model_name, wait)
                        _time.sleep(wait)
                        continue
                    else:
                        reason = "rate-limited (429)" if "429" in err_str else "not available (404)"
                        logger.warning("[MUTATION-LLM] Groq %s %s, trying next model...",
                                       model_name, reason)
                        break
                else:
                    logger.error("[MUTATION-LLM] Groq %s failed after %.2fs: %s",
                                 model_name, elapsed, e)
                    raise RuntimeError(
                        f"LLM call failed (Groq {model_name}): {err_str}. "
                        "Check your API key and network."
                    )
        if model_succeeded:
            break
    return raw_text


def _call_mutation_gemini(
    prompt: str,
    models_to_try: List[str],
) -> Optional[str]:
    """Call Gemini API for mutation parsing. Returns raw text or None."""
    import re as _re
    import time as _time
    from llm_parser import _get_genai_client

    client = _get_genai_client()
    if client is None:
        raise RuntimeError(
            "Could not initialise the Gemini AI client. Ensure the "
            "google-genai SDK is installed (pip install google-genai) and "
            "your GEMINI_API_KEY is valid."
        )

    raw_text = None
    for model_name in models_to_try:
        logger.info("[MUTATION-LLM] Trying Gemini model %s", model_name)
        max_retries = 1
        model_succeeded = False

        for attempt in range(max_retries + 1):
            start = _time.time()
            try:
                from google.genai import types
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=2048,
                    ),
                )
                elapsed = _time.time() - start
                raw_text = response.text
                logger.info("[MUTATION-LLM] Gemini %s responded in %.2fs (%d chars)",
                            model_name, elapsed, len(raw_text))
                model_succeeded = True
                break
            except Exception as e:
                elapsed = _time.time() - start
                err_str = str(e)
                is_retriable = "429" in err_str or "404" in err_str or "NOT_FOUND" in err_str
                if is_retriable:
                    if "429" in err_str and attempt < max_retries:
                        delay_match = _re.search(r"retry(?:Delay)?[^\d]*(\d+)", err_str, _re.IGNORECASE)
                        suggested_delay = int(delay_match.group(1)) if delay_match else 5
                        wait = min(suggested_delay, 8)
                        logger.warning("[MUTATION-LLM] Gemini %s rate-limited, retrying in %ds...",
                                       model_name, wait)
                        _time.sleep(wait)
                        continue
                    else:
                        reason = "rate-limited (429)" if "429" in err_str else "not available (404)"
                        logger.warning("[MUTATION-LLM] Gemini %s %s, trying next model...",
                                       model_name, reason)
                        break
                else:
                    logger.error("[MUTATION-LLM] Gemini %s failed after %.2fs: %s",
                                 model_name, elapsed, e)
                    raise RuntimeError(
                        f"LLM call failed (Gemini {model_name}): {err_str}. "
                        "Check your API key and network."
                    )
        if model_succeeded:
            break
    return raw_text


def _parse_mutation_with_llm(
    query: str,
    allowed_fields: List[str],
    numeric_fields: List[str],
    field_types: Optional[Dict[str, str]] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Use LLM to parse a natural-language CRUD request into a mutation plan.

    Returns the mutation dict on success.
    Raises ``RuntimeError`` with a descriptive message on failure so the
    caller can propagate a helpful detail to the frontend.

    Supports Groq (default) and Gemini providers via LLM_PROVIDER env var.
    Model fallback chain: if the primary model is rate-limited (429), the
    function automatically tries alternative models before giving up.
    """
    import os, re as _re
    from llm_parser import _get_llm_provider

    provider = _get_llm_provider()
    prompt = _build_mutation_prompt(query, allowed_fields, numeric_fields, field_types, history)

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "LLM is not configured — GROQ_API_KEY environment variable is "
                "missing. Set it in your .env file or system environment."
            )
        primary_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        models_to_try = list(dict.fromkeys([
            primary_model,
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ]))
        raw_text = _call_mutation_groq(prompt, models_to_try)
    else:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "LLM is not configured — GEMINI_API_KEY environment variable is "
                "missing. Set it in your .env file or system environment."
            )
        primary_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
        models_to_try = list(dict.fromkeys([
            primary_model,
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
        ]))
        raw_text = _call_mutation_gemini(prompt, models_to_try)

    if raw_text is None:
        provider_name = "Groq" if provider == "groq" else "Gemini"
        raise RuntimeError(
            f"All {provider_name} models are rate-limited (429 quota exceeded). "
            "Options:\n"
            "1. Wait ~1 minute and retry\n"
            "2. Check your API key and quota at your provider's dashboard\n"
            "3. Switch LLM_PROVIDER in .env to use a different provider"
        )

    # --- Robust JSON extraction ---
    # Strip markdown code fences if present
    cleaned = raw_text.strip()
    cleaned = _re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = _re.sub(r"\s*```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    # Try to find a JSON object in the response
    mutation = None
    try:
        mutation = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract the first { ... } block
        brace_match = _re.search(r"\{[\s\S]*\}", cleaned)
        if brace_match:
            try:
                mutation = json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

    if mutation is None:
        # Last resort: try the helper from llm_parser
        from llm_parser import _extract_json
        mutation = _extract_json(raw_text)

    if mutation is None:
        logger.warning("[MUTATION-LLM] Could not extract JSON from: %s", raw_text[:500])
        raise RuntimeError(
            "AI returned an unparseable response. Try rephrasing your query "
            "more explicitly, e.g. 'add field X with value Y to document "
            "with _id Z' or 'delete the document where _id is Z'."
        )

    # --- Auto-fix common LLM mistakes ---
    op = mutation.get("operation", "").lower().strip()
    # Normalise operation aliases
    op_map = {
        "create": "insert", "add": "insert", "new": "insert",
        "put": "update", "set": "update", "modify": "update", "patch": "update",
        "remove": "delete", "drop": "delete", "destroy": "delete",
    }
    op = op_map.get(op, op)
    mutation["operation"] = op

    if op not in ("insert", "update", "delete"):
        logger.warning("[MUTATION-LLM] Invalid operation '%s' from LLM", op)
        raise RuntimeError(
            f"AI returned an unrecognised operation '{op}'. Rephrase your "
            "query to clearly express an insert, update, or delete action."
        )

    # Fix: update with bare field:value instead of $set
    if op == "update" and mutation.get("update"):
        upd = mutation["update"]
        has_operator = any(k.startswith("$") for k in upd)
        if not has_operator:
            # LLM forgot to wrap in $set — fix it automatically
            mutation["update"] = {"$set": upd}
            logger.info("[MUTATION-LLM] Auto-wrapped bare update in $set")

    # Normalise optional keys so downstream code can rely on them
    mutation.setdefault("filter", None)
    mutation.setdefault("update", None)
    mutation.setdefault("document", None)
    mutation.setdefault("documents", None)
    mutation.setdefault("multi", False)
    mutation.setdefault("estimated_affected", None)
    mutation.setdefault("description", f"{op} operation on the collection")

    logger.info("[MUTATION-LLM] Parsed mutation: op=%s, desc=%s",
                op, mutation.get("description", "")[:80])
    return mutation


def _coerce_id_value(raw_val: Any) -> List[Any]:
    """Return a list of _id candidate values to try, most-specific first.

    MongoDB collections use different _id types (string, int, ObjectId).
    Rather than guessing, we generate candidates and let the caller probe
    the collection to find which one actually matches a document.

    Order: original value → int (if numeric string) → ObjectId (if 24-hex) → str.
    Duplicates are removed while preserving order.
    """
    from bson import ObjectId as _OID

    candidates: list = []
    seen: set = set()

    def _add(v: Any) -> None:
        key = (type(v).__name__, str(v))
        if key not in seen:
            seen.add(key)
            candidates.append(v)

    _add(raw_val)  # keep whatever the caller passed first

    str_val = str(raw_val)

    # Numeric string → int (many collections use numeric _id)
    try:
        int_val = int(str_val)
        _add(int_val)
    except (ValueError, TypeError):
        pass

    # 24-char hex → ObjectId
    if len(str_val) == 24:
        try:
            _add(_OID(str_val))
        except Exception:
            pass

    # Always try the plain string form too
    _add(str_val)

    return candidates


def _resolve_filter_id(
    collection: Any,
    filt: Dict[str, Any],
) -> Dict[str, Any]:
    """Given a filter that contains an _id key, probe the real collection
    to find which _id type actually matches a document and return the
    corrected filter.  If none match, return the original filter unchanged.
    """
    if "_id" not in filt:
        return filt

    candidates = _coerce_id_value(filt["_id"])
    for candidate in candidates:
        test_filt = {**filt, "_id": candidate}
        try:
            if collection.count_documents(test_filt, limit=1) > 0:
                return test_filt
        except Exception:
            continue
    # None matched — return with the first candidate (original)
    return filt


def _detect_collection_id_type(collection: Any) -> str:
    """Sample existing documents to detect the dominant _id BSON type.

    Returns one of: 'int', 'objectid', 'string', or 'unknown'.
    """
    from bson import ObjectId as _OID

    sample = list(collection.find({}, {"_id": 1}).limit(20))
    if not sample:
        return "unknown"

    type_counts: Dict[str, int] = {}
    for doc in sample:
        val = doc["_id"]
        if isinstance(val, _OID):
            t = "objectid"
        elif isinstance(val, int):
            t = "int"
        elif isinstance(val, float):
            t = "float"
        else:
            t = "string"
        type_counts[t] = type_counts.get(t, 0) + 1

    # Return the most common type
    return max(type_counts, key=type_counts.get)  # type: ignore[arg-type]


def _coerce_id_to_collection_type(raw_val: Any, collection: Any) -> Any:
    """Coerce a raw _id value to match the dominant _id type in the collection.

    This is critical for INSERT operations — the LLM always produces _id as a
    JSON string, but the collection may use int or ObjectId _id values.
    """
    from bson import ObjectId as _OID

    id_type = _detect_collection_id_type(collection)
    str_val = str(raw_val)

    if id_type == "int":
        try:
            return int(str_val)
        except (ValueError, TypeError):
            return raw_val
    elif id_type == "float":
        try:
            return float(str_val)
        except (ValueError, TypeError):
            return raw_val
    elif id_type == "objectid":
        if isinstance(raw_val, _OID):
            return raw_val
        if len(str_val) == 24:
            try:
                return _OID(str_val)
            except Exception:
                return raw_val
        # Not a valid ObjectId string — let MongoDB auto-generate
        return raw_val
    else:
        # Default to string (or if unknown, keep original)
        return str_val


def _resolve_insert_ids(collection: Any, mutation: Dict[str, Any]) -> Dict[str, Any]:
    """For insert operations, coerce _id values in document(s) to match the
    collection's actual _id type and warn about duplicates.

    Returns the mutation dict with coerced _id values and a
    'duplicate_ids' list if any conflicts are detected.
    """
    duplicates: list = []

    def _fix_doc(doc: dict) -> dict:
        if "_id" not in doc:
            return doc
        coerced = _coerce_id_to_collection_type(doc["_id"], collection)
        doc["_id"] = coerced
        # Check for duplicate
        try:
            # Try all candidates to be thorough
            candidates = _coerce_id_value(coerced)
            for c in candidates:
                if collection.count_documents({"_id": c}, limit=1) > 0:
                    duplicates.append(str(c))
                    break
        except Exception:
            pass
        return doc

    doc = mutation.get("document")
    if doc and isinstance(doc, dict):
        mutation["document"] = _fix_doc(doc)

    docs = mutation.get("documents")
    if docs and isinstance(docs, list):
        mutation["documents"] = [_fix_doc(d) for d in docs if isinstance(d, dict)]

    if duplicates:
        mutation["duplicate_ids"] = duplicates

    return mutation


@app.post("/mutation-preview")
def mutation_preview(request: MutationRequest):
    """Parse a natural-language CRUD request and return a mutation plan
    WITHOUT executing it.  The frontend shows this plan to the user
    for approval before committing.

    Pipeline:
      1. Connect to MongoDB and retrieve / cache the collection schema
      2. Send (query + schema) to LLM (Groq or Gemini)
      3. Validate + normalise the LLM response into a MutationPlan
      4. (For update/delete) Count affected documents + grab samples
      5. Return the preview for human approval
    """

    logger.info("[MUTATION] Preview request: db=%s, coll=%s, query=%s",
                request.database_name, request.collection_name, request.query[:120])

    # ---- 1. Get schema ----
    try:
        allowed_fields, numeric_fields, field_types = get_cached_schema(
            request.mongo_uri, request.database_name, request.collection_name,
        )
    except Exception as e:
        logger.error("[MUTATION] Schema detection failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not connect to MongoDB or detect the schema for "
                f"'{request.database_name}.{request.collection_name}': {e}"
            ),
        )

    logger.info("[MUTATION] Schema: %d fields (%d numeric)",
                len(allowed_fields), len(numeric_fields))

    # ---- 2 & 3. Parse mutation via LLM ----
    try:
        mutation = _parse_mutation_with_llm(
            request.query, allowed_fields, numeric_fields, field_types,
            history=request.history,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ---- 4. Estimate affected documents for update/delete ----
    if mutation["operation"] in ("update", "delete") and mutation.get("filter"):
        try:
            from pymongo import MongoClient
            _client = MongoClient(request.mongo_uri, serverSelectionTimeoutMS=5000)
            try:
                _db = _client[request.database_name]
                _coll = _db[request.collection_name]

                filt = mutation["filter"]

                # Dynamically resolve _id type (string/int/ObjectId)
                if "_id" in filt:
                    filt = _resolve_filter_id(_coll, filt)
                    mutation["filter"] = filt

                count = _coll.count_documents(filt)
                mutation["estimated_affected"] = count

                # Grab a few sample docs that would be affected
                sample_cursor = _coll.find(filt).limit(3)
                sample_docs = []
                for doc in sample_cursor:
                    doc["_id"] = str(doc["_id"])
                    sample_docs.append(_sanitise_value(doc))
                mutation["sample_affected"] = sample_docs
            finally:
                _client.close()
        except Exception as e:
            logger.warning("[MUTATION] Could not estimate affected docs: %s", e)
            mutation["estimated_affected"] = None
            mutation["sample_affected"] = []

    # ---- 4b. For inserts: coerce _id type to match collection + check duplicates ----
    if mutation["operation"] == "insert":
        try:
            from pymongo import MongoClient
            _client = MongoClient(request.mongo_uri, serverSelectionTimeoutMS=5000)
            try:
                _db = _client[request.database_name]
                _coll = _db[request.collection_name]
                mutation = _resolve_insert_ids(_coll, mutation)
                if mutation.get("duplicate_ids"):
                    mutation["warning"] = (
                        f"Document(s) with _id {mutation['duplicate_ids']} already "
                        f"exist. Committing will fail with a duplicate key error."
                    )
                    logger.warning("[MUTATION] Duplicate _id detected: %s",
                                   mutation["duplicate_ids"])
            finally:
                _client.close()
        except Exception as e:
            logger.warning("[MUTATION] Insert _id resolution failed: %s", e)

    # ---- 5. Return preview ----
    logger.info("[MUTATION] Preview ready: op=%s, affected=%s",
                mutation["operation"], mutation.get("estimated_affected"))
    return {
        "status": "preview",
        "query": request.query,
        "mutation": _sanitise_value(mutation),
    }


class EstimateRequest(BaseModel):
    """Request model for counting documents matching a filter (no LLM needed)."""
    mongo_uri: str
    database_name: str
    collection_name: str
    filter: Dict[str, Any] = Field(default_factory=dict)


@app.post("/mutation-estimate")
def mutation_estimate(request: EstimateRequest):
    """Count documents matching a filter and return samples.
    Used by Manual mode to show an estimate WITHOUT invoking the LLM."""
    from pymongo import MongoClient

    logger.info("[MUTATION-ESTIMATE] Counting docs in %s.%s with filter %s",
                request.database_name, request.collection_name,
                json.dumps(request.filter)[:200])
    try:
        client = MongoClient(request.mongo_uri, serverSelectionTimeoutMS=5000)
        try:
            db = client[request.database_name]
            coll = db[request.collection_name]
            count = coll.count_documents(request.filter)
            sample_cursor = coll.find(request.filter).limit(3)
            sample_docs = []
            for doc in sample_cursor:
                doc["_id"] = str(doc["_id"])
                sample_docs.append(_sanitise_value(doc))
        finally:
            client.close()
    except Exception as e:
        logger.warning("[MUTATION-ESTIMATE] Failed: %s", e)
        return {"count": None, "sample_affected": [], "error": str(e)}

    return {"count": count, "sample_affected": sample_docs}


@app.post("/mutation-commit")
def mutation_commit(request: CommitRequest):
    """Execute a previously previewed mutation plan against MongoDB.
    This is the human-approval commit step."""
    from pymongo import MongoClient

    mutation = request.mutation
    op = mutation.get("operation")

    if op not in ("insert", "update", "delete"):
        raise HTTPException(status_code=400, detail=f"Invalid operation: {op}")

    client = MongoClient(request.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        db = client[request.database_name]
        coll = db[request.collection_name]

        # Dynamically resolve _id type in filter (string/int/ObjectId)
        if op in ("update", "delete") and mutation.get("filter") and "_id" in mutation["filter"]:
            mutation["filter"] = _resolve_filter_id(coll, mutation["filter"])

        # Dynamically coerce _id type in insert documents to match collection
        if op == "insert":
            mutation = _resolve_insert_ids(coll, mutation)

        result_info: Dict[str, Any] = {"operation": op, "status": "committed"}

        if op == "insert":
            doc = mutation.get("document")
            docs = mutation.get("documents")
            if docs and isinstance(docs, list) and len(docs) > 0:
                insert_result = coll.insert_many(docs)
                result_info["inserted_count"] = len(insert_result.inserted_ids)
                result_info["inserted_ids"] = [str(oid) for oid in insert_result.inserted_ids]
            elif doc and isinstance(doc, dict):
                insert_result = coll.insert_one(doc)
                result_info["inserted_count"] = 1
                result_info["inserted_id"] = str(insert_result.inserted_id)
            else:
                raise HTTPException(status_code=400, detail="Insert requires 'document' or 'documents'")

        elif op == "update":
            filt = mutation.get("filter") or {}
            update_doc = mutation.get("update")
            if not update_doc:
                raise HTTPException(status_code=400, detail="Update requires 'update' field")
            # Auto-fix: if update has no $ operators, wrap in $set
            if not any(k.startswith("$") for k in update_doc):
                update_doc = {"$set": update_doc}
            multi = mutation.get("multi", False)
            if multi:
                update_result = coll.update_many(filt, update_doc)
            else:
                update_result = coll.update_one(filt, update_doc)
            result_info["matched_count"] = update_result.matched_count
            result_info["modified_count"] = update_result.modified_count

        elif op == "delete":
            filt = mutation.get("filter") or {}
            multi = mutation.get("multi", False)
            if multi:
                delete_result = coll.delete_many(filt)
            else:
                delete_result = coll.delete_one(filt)
            result_info["deleted_count"] = delete_result.deleted_count

        # Invalidate schema cache for this collection since data changed
        invalidate_schema(request.mongo_uri, request.database_name, request.collection_name)

        logger.info("[MUTATION] Committed %s on %s.%s: %s",
                     op, request.database_name, request.collection_name, result_info)

        # Log commit activity (fire-and-forget)
        try:
            log_activity(
                request.mongo_uri, request.database_name,
                activity_type=ACTIVITY_COMMIT,
                collection_name=request.collection_name,
                user_email=getattr(request, "user_email", "anonymous") or "anonymous",
                query=mutation.get("description", op),
                details={
                    "operation": op,
                    **{k: v for k, v in result_info.items() if k != "status"},
                },
            )
        except Exception:
            pass

        return result_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MUTATION] Commit failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Mutation commit failed: {e}")
    finally:
        client.close()


# ====================== ANALYTICS / DASHBOARD ENDPOINTS ======================


class AnalyticsRequest(BaseModel):
    """Request model for dashboard analytics endpoints."""
    mongo_uri: str
    database_name: str
    user_email: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    days: int = Field(default=30, ge=1, le=365, description="Lookback window in days")
    hours: Optional[int] = Field(default=None, ge=1, le=8760, description="Lookback window in hours (overrides days)")
    minutes: Optional[int] = Field(default=None, ge=1, le=525600, description="Lookback window in minutes (overrides hours/days)")
    granularity: str = Field(default="auto", description="Time bucket granularity: auto, minute, hour, day, month")


def _resolve_lookback_minutes(request: AnalyticsRequest) -> Optional[int]:
    """Convert the user's time filter (minutes/hours/days) into total minutes."""
    if request.minutes:
        return request.minutes
    if request.hours:
        return request.hours * 60
    if request.days:
        return request.days * 24 * 60
    return None


@app.post("/analytics/commit-timeline")
def commit_timeline(request: AnalyticsRequest):
    """Return recent commit events for the commit-tracking chart."""
    try:
        lookback_mins = _resolve_lookback_minutes(request)
        data = get_commit_timeline(
            request.mongo_uri,
            request.database_name,
            user_email=request.user_email,
            lookback_minutes=lookback_mins,
        )
        return {"timeline": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load commit timeline: {e}")


@app.post("/analytics/stats")
def activity_stats(request: AnalyticsRequest):
    """Return aggregated activity stats (totals, daily/hourly/minute breakdown, severity, top collections)."""
    try:
        lookback_mins = _resolve_lookback_minutes(request)
        data = get_activity_stats(
            request.mongo_uri,
            request.database_name,
            user_email=request.user_email,
            year=request.year,
            month=request.month,
            day=request.day,
            lookback_minutes=lookback_mins,
            granularity=request.granularity,
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load stats: {e}")


@app.post("/analytics/diagnosis-monthly")
def diagnosis_monthly(request: AnalyticsRequest):
    """Return diagnosis events aggregated by month/day/hour with severity scores."""
    try:
        data = get_diagnosis_monthly(
            request.mongo_uri,
            request.database_name,
            user_email=request.user_email,
            year=request.year,
            month=request.month,
            day=request.day,
            granularity=request.granularity,
        )
        return {"monthly": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load diagnosis data: {e}")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/llm-status")
def llm_status():
    """Check whether the LLM parser is configured and available."""
    import os
    from llm_parser import _get_llm_provider

    provider = _get_llm_provider()
    mode = PARSER_MODE

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        has_key = bool(api_key)
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        sdk_available = False
        try:
            import groq  # noqa: F401
            sdk_available = True
        except ImportError:
            pass
        sdk_name = "groq"
    else:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        has_key = bool(api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        sdk_available = False
        try:
            from google import genai  # noqa: F401
            sdk_available = True
        except ImportError:
            pass
        sdk_name = "google-genai"

    return {
        "llm_configured": has_key and sdk_available,
        "api_key_set": has_key,
        "sdk_installed": sdk_available,
        "provider": provider,
        "model": model,
        "parser_mode": mode,
        "info": (
            f"LLM parser active ({provider}/{model}) — queries parsed via AI "
            "with rule-based fallback"
            if has_key and sdk_available
            else f"LLM parser inactive — using rule-based parser only. "
                 f"Set {'GROQ_API_KEY' if provider == 'groq' else 'GEMINI_API_KEY'} "
                 f"env var and install {sdk_name}."
        ),
    }