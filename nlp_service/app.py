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
from response_formatter import format_response
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


class SchemaRequest(BaseModel):
    mongo_uri: str
    database_name: str
    collection_name: str


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
        sample_doc.pop("_id", None)
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
                _sample.pop("_id", None)
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

    return trace


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/llm-status")
def llm_status():
    """Check whether the LLM parser is configured and available."""
    import os
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    has_key = bool(api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    mode = PARSER_MODE

    sdk_available = False
    try:
        from google import genai  # noqa: F401
        sdk_available = True
    except ImportError:
        pass

    return {
        "llm_configured": has_key and sdk_available,
        "api_key_set": has_key,
        "sdk_installed": sdk_available,
        "model": model,
        "parser_mode": mode,
        "info": (
            "LLM parser active — queries parsed via AI with rule-based fallback"
            if has_key and sdk_available
            else "LLM parser inactive — using rule-based parser only. "
                 "Set GEMINI_API_KEY env var and install google-generativeai."
        ),
    }