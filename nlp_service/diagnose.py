#!/usr/bin/env python3
"""
NLP MongoDB Interface — Diagnostic Script
==========================================

Usage:
    python diagnose.py <mongo_uri> <database> <collection> "<query>"

Example:
    python diagnose.py "mongodb://localhost:27017" mydb mycollection "show records where options is Order"

This script calls the /diagnose-schema and /diagnose endpoints and
prints a step-by-step trace of the entire NLP pipeline so you can see
exactly where a query fails or produces unexpected results.

Requires: requests  (pip install requests)
"""

import sys
import json

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests")
    sys.exit(1)

BASE_URL = "http://localhost:8000"

SEPARATOR = "=" * 70
DASH = "-" * 40


def colour(text, code):
    """ANSI colour wrapper (no-op on Windows without colorama)."""
    return f"\033[{code}m{text}\033[0m"


def green(t):  return colour(t, 32)
def red(t):    return colour(t, 31)
def yellow(t): return colour(t, 33)
def cyan(t):   return colour(t, 36)
def bold(t):   return colour(t, 1)


def diagnose_schema(payload):
    print(f"\n{SEPARATOR}")
    print(bold("STEP 0 — SCHEMA INSPECTION  (POST /diagnose-schema)"))
    print(SEPARATOR)

    try:
        resp = requests.post(f"{BASE_URL}/diagnose-schema", json=payload, timeout=10)
        data = resp.json()
    except Exception as e:
        print(red(f"  ERROR: {e}"))
        return

    # Sample document field types
    if data.get("sample_doc_types"):
        print(cyan("\n  Raw document field types (1 sample doc):"))
        for k, v in data["sample_doc_types"].items():
            print(f"    {k}: {v}")

    # Flattened fields
    if data.get("flattened_fields"):
        print(cyan("\n  Flattened fields (dot-notation):"))
        for k, v in data["flattened_fields"].items():
            print(f"    {green(k)}: {v}")

    # Summary
    print(f"\n  {bold('Total fields:')} {data.get('field_count', '?')}")
    print(f"  {bold('Allowed fields:')} {data.get('allowed_fields', [])}")
    print(f"  {bold('Numeric fields:')} {data.get('numeric_fields', [])}")

    return data.get("allowed_fields", [])


def diagnose_query(payload):
    print(f"\n{SEPARATOR}")
    print(bold(f"FULL PIPELINE DIAGNOSIS  (POST /diagnose)"))
    print(f"  Query: \"{payload['query']}\"")
    print(SEPARATOR)

    try:
        resp = requests.post(f"{BASE_URL}/diagnose", json=payload, timeout=15)
        data = resp.json()
    except Exception as e:
        print(red(f"  ERROR: {e}"))
        return

    steps = data.get("steps", {})

    # Step 1 — Schema
    s1 = steps.get("1_schema", {})
    print(f"\n{DASH}")
    print(bold("  Step 1 — Schema Detection"))
    if s1.get("status") == "ok":
        print(f"    {green('OK')} — {s1['field_count']} fields detected")
        print(f"    Fields: {s1['allowed_fields']}")
    else:
        print(f"    {red('FAIL')} — {s1.get('error')}")
        return

    # Step 2 — Parse
    s2 = steps.get("2_parse", {})
    print(f"\n{DASH}")
    print(bold("  Step 2 — NL Parser (raw IR)"))
    if s2.get("status") == "ok":
        ir = s2["raw_ir"]
        print(f"    {green('OK')} — operation: {ir.get('operation')}")
        print(f"    conditions: {json.dumps(ir.get('conditions', []), indent=6)}")
        print(f"    aggregation: {ir.get('aggregation')}")
        print(f"    sort: {ir.get('sort')}")
        print(f"    limit: {ir.get('limit')}")
        print(f"    projection: {ir.get('projection')}")

        # Highlight the key diagnostic: what field did the parser pick?
        conds = ir.get("conditions", [])
        if conds:
            for c in conds:
                field = c.get("field", "?")
                val = c.get("value", "?")
                op = c.get("operator", "?")
                print(f"    {yellow(f'→ Parser chose field: \"{field}\"  operator: \"{op}\"  value: \"{val}\"')}")
    else:
        print(f"    {red('FAIL')} — {s2.get('error')}")
        return

    # Step 3 — Field Resolution
    s3 = steps.get("3_resolve", [])
    print(f"\n{DASH}")
    print(bold("  Step 3 — Field Resolution"))
    if s3:
        for entry in s3:
            raw = entry["raw_field"]
            resolved = entry.get("resolved_field")
            ctx = entry.get("context", "condition")
            if entry["matched"]:
                if raw != resolved:
                    print(f"    {green('RESOLVED')} [{ctx}] \"{raw}\" → \"{resolved}\"")
                else:
                    print(f"    {green('EXACT')}    [{ctx}] \"{raw}\"")
            else:
                print(f"    {red('NOT FOUND')} [{ctx}] \"{raw}\" — no matching schema field!")
    else:
        print(f"    (no fields to resolve)")

    # Step 4 — Validate
    s4 = steps.get("4_validate", {})
    print(f"\n{DASH}")
    print(bold("  Step 4 — IR Validation"))
    if s4.get("status") == "ok":
        vir = s4["validated_ir"]
        print(f"    {green('OK')}")
        vconds = vir.get("conditions", [])
        for c in vconds:
            print(f"    → Validated field: \"{c['field']}\"  op: \"{c['operator']}\"  val: \"{c['value']}\"")
    else:
        print(f"    {red('FAIL')} — {s4.get('error')}")
        return

    # Step 5 — Compile
    s5 = steps.get("5_compile", {})
    print(f"\n{DASH}")
    print(bold("  Step 5 — MongoDB Query Compilation"))
    if s5.get("status") == "ok":
        print(f"    {green('OK')} — type: {s5.get('type')}")
        print(f"    filter:   {s5.get('filter')}")
        print(f"    sort:     {s5.get('sort')}")
        print(f"    limit:    {s5.get('limit')}")
        if s5.get("pipeline"):
            print(f"    pipeline: {s5.get('pipeline')}")
    else:
        print(f"    {red('error')}: {s5}")

    # Step 6 — Execute preview
    s6 = steps.get("6_execute_preview", {})
    print(f"\n{DASH}")
    print(bold("  Step 6 — Execution Preview"))
    if s6.get("status") == "ok":
        total = s6.get("total_count", 0)
        returned = s6.get("returned", 0)
        if total > 0:
            print(f"    {green(f'OK — {total} total documents matched, showing {returned}')}")
            for i, doc in enumerate(s6.get("sample_docs", []), 1):
                print(f"    Doc {i}: {json.dumps(doc, default=str)[:300]}")
        else:
            print(f"    {red('0 DOCUMENTS MATCHED')}")
            print(f"    {yellow('→ The filter compiled but matched nothing in MongoDB.')}")
            print(f"    {yellow('  Check: is the field correct? Is the value spelled correctly?')}")
            print(f"    {yellow('  Filter was: ' + s5.get('filter', '?'))}")
    else:
        print(f"    {red('ERROR')} — {s6.get('error')}")

    # Step 7 — Index info
    s7 = steps.get("7_index_info", {})
    print(f"\n{DASH}")
    print(bold("  Step 7 — Index Info"))
    if s7.get("unindexed_fields"):
        print(f"    {yellow('Unindexed queried fields: ' + ', '.join(s7['unindexed_fields']))}")
    else:
        print(f"    {green('All queried fields are indexed (or no conditions)')}")

    print(f"\n{SEPARATOR}")
    print(bold("DIAGNOSIS COMPLETE"))
    print(SEPARATOR)


def main():
    if len(sys.argv) < 5:
        print(bold("NLP MongoDB Diagnostic Tool"))
        print()
        print("Usage:")
        print(f"  python {sys.argv[0]} <mongo_uri> <database> <collection> \"<query>\"")
        print()
        print("Examples:")
        print(f'  python {sys.argv[0]} "mongodb://localhost:27017" testdb orders "show records where options is Order"')
        print(f'  python {sys.argv[0]} "mongodb://localhost:27017" testdb users "find city is mumbai"')
        print()
        print("The server must be running at http://localhost:8000")
        print()

        # Interactive mode
        print(bold("Interactive mode:"))
        mongo_uri = input("  MongoDB URI: ").strip() or "mongodb://localhost:27017"
        database = input("  Database name: ").strip()
        collection = input("  Collection name: ").strip()
        query = input("  NL query: ").strip()
    else:
        mongo_uri = sys.argv[1]
        database = sys.argv[2]
        collection = sys.argv[3]
        query = sys.argv[4]

    if not database or not collection or not query:
        print(red("Error: database, collection, and query are required"))
        sys.exit(1)

    payload = {
        "mongo_uri": mongo_uri,
        "database_name": database,
        "collection_name": collection,
        "query": query,
    }

    # Check server health
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        if r.status_code == 200:
            print(green(f"Server is healthy (v{r.json().get('version', '?')})"))
        else:
            print(red("Server returned non-200 status"))
    except Exception:
        print(red(f"Cannot reach server at {BASE_URL} — is uvicorn running?"))
        sys.exit(1)

    # Run diagnostics
    schema_fields = diagnose_schema(payload)
    diagnose_query(payload)


if __name__ == "__main__":
    main()
