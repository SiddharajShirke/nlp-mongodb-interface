"""
LLM-based natural language query parser using Google Gemini.

This module provides an AI-powered parser that understands ANY natural language
query pattern — including complex nested queries, array literals, sub-queries,
and colloquial human language — by leveraging a large language model.

Architecture:
    User Query + Schema  →  LLM Prompt  →  Gemini API  →  JSON IR

The LLM parser serves as the PRIMARY parser, with the rule-based ``parser.py``
as an automatic fallback when:
    - No API key is configured
    - The ``google-generativeai`` package is not installed
    - The LLM call fails (network, rate limits, etc.)
    - The LLM response cannot be parsed into valid IR

Output format is identical to ``parser.parse_to_ir()``, ensuring full
compatibility with the downstream pipeline
(``ir_validator`` → ``ir_compiler`` → ``db_executor``).
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from logger import logger

# ---------------------------------------------------------------------------
# Lazy-load the Gemini SDK so the rest of the app works even when
# google-genai is not installed.
# ---------------------------------------------------------------------------
_genai_client = None


def _get_genai_client():
    global _genai_client
    if _genai_client is None:
        try:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            if not api_key:
                return None
            _genai_client = genai.Client(api_key=api_key)
        except ImportError:
            logger.warning(
                "google-genai is not installed. "
                "Run: pip install google-genai"
            )
            return None
    return _genai_client


# ---------------------------------------------------------------------------
# IR structure validation
# ---------------------------------------------------------------------------
ALLOWED_OPERATORS = frozenset({
    "eq", "gt", "lt", "gte", "lte", "in", "ne", "exists", "contains",
})


def _validate_ir_structure(
    ir: Dict[str, Any],
    allowed_fields: List[str],
) -> bool:
    """Return ``True`` if the LLM-generated IR has a valid structure."""
    if not isinstance(ir, dict):
        return False

    if ir.get("operation") not in ("find", "aggregate"):
        return False

    # --- conditions ---
    conditions = ir.get("conditions")
    if not isinstance(conditions, list):
        return False
    allowed_lower = {f.lower() for f in allowed_fields}
    # Also allow last-segment matches (e.g. "city" → "address.city")
    last_segments = set()
    for f in allowed_fields:
        if "." in f:
            last_segments.add(f.rsplit(".", 1)[-1].lower())

    for cond in conditions:
        if not isinstance(cond, dict):
            return False
        if not {"field", "operator", "value"} <= cond.keys():
            return False
        if cond["operator"] not in ALLOWED_OPERATORS:
            return False
        fl = cond["field"].lower()
        if fl not in allowed_lower and fl not in last_segments:
            logger.warning("[LLM-validate] unknown field: %s", cond["field"])
            return False

    # --- aggregation ---
    agg = ir.get("aggregation")
    if agg is not None:
        if not isinstance(agg, dict):
            return False
        if agg.get("type") not in ("count", "avg", "sum", "max", "min"):
            return False

    # --- sort ---
    sort_val = ir.get("sort")
    if sort_val is not None:
        if not isinstance(sort_val, dict):
            return False
        if sort_val.get("direction") not in ("asc", "desc"):
            return False

    # --- limit ---
    limit = ir.get("limit")
    if limit is not None and not isinstance(limit, int):
        return False

    # --- projection ---
    proj = ir.get("projection")
    if proj is not None and not isinstance(proj, list):
        return False

    return True


def _fix_field_names(
    ir: Dict[str, Any],
    allowed_fields: List[str],
) -> Dict[str, Any]:
    """Re-case LLM-produced field names to match the schema exactly."""
    # Build lookup: lower-case → schema field name
    field_map: Dict[str, str] = {}
    for f in allowed_fields:
        field_map[f.lower()] = f
    # Also map last segments (lower) → full dotted path
    for f in allowed_fields:
        if "." in f:
            last = f.rsplit(".", 1)[-1].lower()
            field_map.setdefault(last, f)

    def _fix(name: str) -> str:
        return field_map.get(name.lower(), name)

    for cond in ir.get("conditions", []):
        cond["field"] = _fix(cond["field"])

    agg = ir.get("aggregation")
    if agg and agg.get("field") and agg["field"] != "*":
        agg["field"] = _fix(agg["field"])

    sort_val = ir.get("sort")
    if sort_val and sort_val.get("field"):
        sort_val["field"] = _fix(sort_val["field"])

    proj = ir.get("projection")
    if proj:
        ir["projection"] = [_fix(p) for p in proj]

    return ir


# ---------------------------------------------------------------------------
# Post-LLM sanitisation — prevent hallucinated / invalid values
# ---------------------------------------------------------------------------

def _sanitize_ir_values(
    ir: Dict[str, Any],
    allowed_fields: List[str],
    field_types: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    """Clean up LLM output values to prevent hallucination issues.

    1. Remove conditions that reference non-existent fields.
    2. Ensure date fields don't use ``contains`` operator (unsupported).
    3. Strip any extra keys the LLM may have invented.
    4. Ensure projection only contains schema fields.
    5. Clamp/remove unreasonable limits.
    """
    allowed_lower = {f.lower() for f in allowed_fields}
    # Also allow last-segment matches
    last_segments: Dict[str, str] = {}
    for f in allowed_fields:
        if "." in f:
            last_segments[f.rsplit(".", 1)[-1].lower()] = f

    ft = field_types or {}

    # --- Filter out conditions with unknown fields ---
    clean_conditions = []
    for cond in ir.get("conditions", []):
        fl = cond.get("field", "").lower()
        if fl not in allowed_lower and fl not in last_segments:
            logger.warning(
                "[LLM-sanitize] Dropping condition with unknown field: %s",
                cond.get("field"),
            )
            continue

        # Fix: date fields should not use "contains" (regex)
        ftype = ft.get(cond.get("field", ""))
        if ftype == "date" and cond.get("operator") == "contains":
            logger.info(
                "[LLM-sanitize] Converting contains→eq for date field: %s",
                cond["field"],
            )
            cond["operator"] = "eq"

        # Fix: numeric fields should have numeric values for comparison ops
        if ftype in ("int", "float") and cond.get("operator") in (
            "eq", "gt", "lt", "gte", "lte", "ne",
        ):
            val = cond.get("value")
            if isinstance(val, str):
                try:
                    cond["value"] = int(val)
                except ValueError:
                    try:
                        cond["value"] = float(val)
                    except ValueError:
                        pass

        clean_conditions.append(cond)

    ir["conditions"] = clean_conditions

    # --- Sanitise projection ---
    proj = ir.get("projection")
    if proj and isinstance(proj, list):
        clean_proj = []
        for p in proj:
            pl = p.lower()
            if pl in allowed_lower or pl in last_segments:
                clean_proj.append(p)
            else:
                logger.warning(
                    "[LLM-sanitize] Dropping unknown projection field: %s", p,
                )
        ir["projection"] = clean_proj if clean_proj else None

    # --- Remove any extra keys the LLM invented ---
    valid_keys = {
        "operation", "conditions", "aggregation", "sort",
        "limit", "projection", "meta",
    }
    extra = set(ir.keys()) - valid_keys
    for k in extra:
        logger.warning("[LLM-sanitize] Removing hallucinated key: %s", k)
        del ir[k]

    # --- Clamp unreasonable limits ---
    limit = ir.get("limit")
    if limit is not None:
        if not isinstance(limit, int) or limit <= 0:
            ir["limit"] = None
        elif limit > 100:
            ir["limit"] = 100

    return ir


# ---------------------------------------------------------------------------
# JSON extraction from LLM text
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first valid JSON object from *text*.

    Handles plain JSON, markdown code-fenced JSON, and surrounding prose.
    """
    text = text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Markdown code block
    for pattern in (
        r"```json\s*\n?(.*?)\n?\s*```",
        r"```\s*\n?(.*?)\n?\s*```",
    ):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue

    # 3. Find outermost { … } — greedy, balanced braces
    depth = 0
    start_idx = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start_idx = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start_idx is not None:
                try:
                    return json.loads(text[start_idx : i + 1])
                except json.JSONDecodeError:
                    start_idx = None

    return None


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_schema_block(
    allowed_fields: List[str],
    numeric_fields: List[str],
    field_types: Optional[Dict[str, str]],
) -> str:
    """Concise schema description for the system prompt."""
    lines: List[str] = []
    for field in allowed_fields:
        ftype = (field_types or {}).get(field, "unknown")
        tag = " [numeric]" if field in numeric_fields else ""
        lines.append(f"  - {field} ({ftype}){tag}")
    return "\n".join(lines)


def _build_prompt(
    query: str,
    allowed_fields: List[str],
    numeric_fields: List[str],
    field_types: Optional[Dict[str, str]],
) -> str:
    """Build the full prompt sent to the LLM."""
    schema_block = _build_schema_block(
        allowed_fields, numeric_fields, field_types,
    )

    # Use double-braces {{ }} to escape literal JSON braces inside f-string
    return f"""You are a MongoDB natural language query parser.  Convert the
user's natural language query into a structured JSON object that describes
the query intent, based on the database schema provided below.

DATABASE SCHEMA:
{schema_block}

OUTPUT FORMAT — respond with ONLY a raw JSON object (no markdown fencing,
no explanation, no extra text):
{{
  "operation": "find" | "aggregate",
  "conditions": [
    {{"field": "<exact field name from schema>", "operator": "<op>", "value": <value>}}
  ],
  "aggregation": null | {{"type": "count|avg|sum|max|min", "field": "<field>"}},
  "sort": null | {{"field": "<field>", "direction": "asc|desc"}},
  "limit": null | <integer>,
  "projection": null | ["<field1>", "<field2>"]
}}

AVAILABLE OPERATORS:
  eq       – exact match (numbers: strict; strings: case-insensitive)
  gt / lt  – greater / less than (works on numbers AND dates)
  gte / lte – greater-or-equal / less-or-equal (works on numbers AND dates)
  ne       – not equal
  in       – value MUST be an array; matches if field equals ANY element
  contains – partial substring match (case-insensitive, strings only)
  exists   – value is true (field present) or false (field absent)

CRITICAL RULES:
 1. Field names MUST exactly match the schema (case-sensitive, dot-notation).
 2. Numeric values must be JSON numbers, not strings (50000, not "50000").
 3. For the "in" operator the value MUST be an array: ["a","b"].
 4. Use "aggregate" ONLY when the user asks for count / avg / sum / max / min.
 5. Use "find" for listing, filtering, showing, or searching.
 6. Empty conditions [] = match all documents.
 7. If the query contains an explicit array literal like ["x","y","z"], use
    operator "eq" with that array as the value (exact array match in MongoDB).
 8. Default limit to 20 for open-ended "show all" queries; omit limit for
    specific look-ups.
 9. Include projection ONLY when the user explicitly asks for specific fields.
10. For "count" / "how many" requests use aggregate with type "count" and
    field "*".
11. DATE/TIME RULES:
    - For date/time fields (type "date"), use ISO 8601 format: "YYYY-MM-DD"
      or "YYYY-MM-DDTHH:MM:SS".
    - "after <date>" → operator "gt", "before <date>" → operator "lt".
    - "since <date>" or "from <date>" → operator "gte".
    - "between <date1> and <date2>" → TWO conditions: gte and lte.
    - "in <year>" → gte "YYYY-01-01" and lte "YYYY-12-31".
    - NEVER use "contains" or "$regex" on date fields — use gt/lt/gte/lte/eq.
    - For relative times like "last 30 days", "yesterday", "this month",
      calculate the actual ISO date.
12. ONLY use field names that exist in the DATABASE SCHEMA above. Do NOT
    invent, guess, or hallucinate field names.
13. When the user asks for a specific record by ID, use "eq" with the exact
    value provided.

EXAMPLES:

Query: "show all records"
{{"operation":"find","conditions":[],"aggregation":null,"sort":null,"limit":20,"projection":null}}

Query: "find employees with salary greater than 50000"
{{"operation":"find","conditions":[{{"field":"salary","operator":"gt","value":50000}}],"aggregation":null,"sort":null,"limit":null,"projection":null}}

Query: "show name and email of users in Sales department"
{{"operation":"find","conditions":[{{"field":"department","operator":"eq","value":"Sales"}}],"aggregation":null,"sort":null,"limit":null,"projection":["name","email"]}}

Query: "top 5 products sorted by price descending"
{{"operation":"find","conditions":[],"aggregation":null,"sort":{{"field":"price","direction":"desc"}},"limit":5,"projection":null}}

Query: "count orders where status is completed"
{{"operation":"aggregate","conditions":[{{"field":"status","operator":"eq","value":"completed"}}],"aggregation":{{"type":"count","field":"*"}},"sort":null,"limit":null,"projection":null}}

Query: "show row with cast [\\"Pearl White\\",\\"Crane Wilbur\\"]"
{{"operation":"find","conditions":[{{"field":"cast","operator":"eq","value":["Pearl White","Crane Wilbur"]}}],"aggregation":null,"sort":null,"limit":null,"projection":null}}

Query: "find movies where genre contains action"
{{"operation":"find","conditions":[{{"field":"genre","operator":"contains","value":"action"}}],"aggregation":null,"sort":null,"limit":null,"projection":null}}

Query: "average salary of employees"
{{"operation":"aggregate","conditions":[],"aggregation":{{"type":"avg","field":"salary"}},"sort":null,"limit":null,"projection":null}}

Query: "show records where date is after 2020-01-01"
{{"operation":"find","conditions":[{{"field":"date","operator":"gt","value":"2020-01-01"}}],"aggregation":null,"sort":null,"limit":null,"projection":null}}

Query: "find comments from 1975"
{{"operation":"find","conditions":[{{"field":"date","operator":"gte","value":"1975-01-01"}},{{"field":"date","operator":"lte","value":"1975-12-31"}}],"aggregation":null,"sort":null,"limit":null,"projection":null}}

Query: "show records between January 2020 and March 2020"
{{"operation":"find","conditions":[{{"field":"date","operator":"gte","value":"2020-01-01"}},{{"field":"date","operator":"lte","value":"2020-03-31"}}],"aggregation":null,"sort":null,"limit":null,"projection":null}}

Query: "find products with price between 100 and 500"
{{"operation":"find","conditions":[{{"field":"price","operator":"gte","value":100}},{{"field":"price","operator":"lte","value":500}}],"aggregation":null,"sort":null,"limit":null,"projection":null}}

Now parse this query:

USER QUERY: "{query}"

Important: Respond ONLY with the JSON object. No explanation, no markdown."""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_with_llm(
    query: str,
    allowed_fields: List[str],
    numeric_fields: List[str],
    field_types: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """Parse a natural language query using Google Gemini.

    Returns the same IR dict as ``parser.parse_to_ir()``, or ``None`` if:
      - No API key is configured (``GEMINI_API_KEY`` env var)
      - ``google-generativeai`` is not installed
      - The LLM call fails
      - The response cannot be parsed into valid IR

    Callers should fall back to ``parser.parse_to_ir()`` when this returns
    ``None``.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.debug("No GEMINI_API_KEY — skipping LLM parser")
        return None

    client = _get_genai_client()
    if client is None:
        return None

    # ---- Configure & call Gemini ----
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    prompt = _build_prompt(query, allowed_fields, numeric_fields, field_types)

    # Retry up to 2 times on transient 429 rate-limit errors
    max_retries = 2
    raw_text = None
    elapsed = 0.0

    for attempt in range(max_retries + 1):
        start = time.time()
        try:
            from google.genai import types
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,       # fully deterministic, no hallucination
                    max_output_tokens=1024,
                ),
            )
            elapsed = time.time() - start
            raw_text = response.text
            logger.info(
                "[LLM] Gemini responded in %.2fs (%d chars)",
                elapsed, len(raw_text),
            )
            logger.debug("[LLM] Raw response: %s", raw_text[:500])
            break  # success
        except Exception as e:
            elapsed = time.time() - start
            err_str = str(e)
            if "429" in err_str and attempt < max_retries:
                wait = 4 * (attempt + 1)  # 4s, 8s backoff
                logger.warning(
                    "[LLM] Rate limited (attempt %d/%d), retrying in %ds...",
                    attempt + 1, max_retries + 1, wait,
                )
                time.sleep(wait)
                continue
            logger.error("[LLM] Gemini call failed after %.2fs: %s", elapsed, e)
            return None

    if raw_text is None:
        return None

    # ---- Extract & validate JSON ----
    ir = _extract_json(raw_text)
    if ir is None:
        logger.warning(
            "[LLM] Could not extract JSON from response: %s",
            raw_text[:300],
        )
        return None

    # Fix field-name casing so downstream validation passes
    ir = _fix_field_names(ir, allowed_fields)

    # Sanitise values — drop hallucinated fields, fix date operators, etc.
    ir = _sanitize_ir_values(ir, allowed_fields, field_types)

    if not _validate_ir_structure(ir, allowed_fields):
        logger.warning(
            "[LLM] IR structure validation failed: %s",
            json.dumps(ir)[:300],
        )
        return None

    # ---- Normalise & enrich ----
    ir.setdefault("operation", "find")
    ir.setdefault("conditions", [])
    ir.setdefault("aggregation", None)
    ir.setdefault("sort", None)
    ir.setdefault("limit", None)
    ir.setdefault("projection", None)

    ir["meta"] = {
        "confidence": 0.95,
        "needs_clarification": False,
        "parser": "llm",
        "model": model_name,
        "latency_ms": int(elapsed * 1000),
    }

    logger.info(
        "[LLM] Parsed OK: operation=%s, conditions=%d, agg=%s, sort=%s, "
        "limit=%s, projection=%s",
        ir["operation"],
        len(ir["conditions"]),
        ir.get("aggregation", {}).get("type") if ir.get("aggregation") else None,
        ir.get("sort"),
        ir.get("limit"),
        ir.get("projection"),
    )

    return ir
