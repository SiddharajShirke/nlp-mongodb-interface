# 🗄️ NLP MongoDB Interface

> **A production-grade Natural Language Interface for MongoDB** — query any MongoDB collection using plain English. Powered by Google Gemini LLM with an intelligent rule-based fallback parser.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://reactjs.org/)
[![Node.js](https://img.shields.io/badge/Node.js-Express%205-339933.svg)](https://expressjs.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Any%20Version-47A248.svg)](https://www.mongodb.com/)

---

## 📖 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Detailed Component Breakdown](#detailed-component-breakdown)
  - [Frontend (React)](#1-frontend-react)
  - [API Gateway (Node.js/Express)](#2-api-gateway-nodejsexpress)
  - [NLP Service (Python/FastAPI)](#3-nlp-service-pythonfastapi)
- [NLP Pipeline — End-to-End Workflow](#nlp-pipeline--end-to-end-workflow)
- [API Endpoints Reference](#api-endpoints-reference)
- [Intermediate Representation (IR) Format](#intermediate-representation-ir-format)
- [Parser Modes](#parser-modes)
- [Key Features](#key-features)
- [Installation & Setup](#installation--setup)
- [Environment Variables](#environment-variables)
- [Usage Examples](#usage-examples)
- [Diagnostic Tools](#diagnostic-tools)
- [Configuration](#configuration)

---

## Overview

**NLP MongoDB Interface** allows users to connect to **any** MongoDB cluster and query collections using natural language — no knowledge of MongoDB query syntax required. The system translates plain English queries into optimized MongoDB operations via a multi-stage NLP pipeline.

**Example queries:**
```
"show all employees in Mumbai"
"average salary where department is Engineering"
"count users who joined after 2023"
"top 10 products sorted by price descending"
"show name, email where age greater than 30"
```

The application follows a **3-tier microservices architecture**:

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────┐
│  React   │────▶│  Express.js  │────▶│   FastAPI     │────▶│ MongoDB │
│ Frontend │◀────│  API Gateway │◀────│  NLP Service  │◀────│ Cluster │
└──────────┘     └──────────────┘     └──────────────┘     └─────────┘
  :3000            :5000                :8000
```

---

## Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER (Browser)                                 │
│                         http://localhost:3000                                │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React 19)                                  │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Step 1:   │  │ Step 2:      │  │ Step 3:      │  │ Step 4:           │  │
│  │ Connect   │─▶│ Select DB    │─▶│ Select       │─▶│ NL Query +        │  │
│  │ Cluster   │  │              │  │ Collection   │  │ Results Table     │  │
│  └───────────┘  └──────────────┘  └──────────────┘  └───────────────────┘  │
│                              api.js (Axios)                                 │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │  HTTP POST/GET
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY (Express 5 + Node.js)                        │
│                        http://localhost:5000                                 │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │  /api/nlq/*  routes  →  nlqController.js  (proxy layer) │               │
│  │    - /connect-cluster    - /run-nlp        - /diagnose   │               │
│  │    - /get-collections    - /run-nlp-stream - /clear-cache│               │
│  │    - /get-schema         - /get-indexes    - /llm-status │               │
│  └──────────────────────────────────────────────────────────┘               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │  HTTP (Axios → FastAPI)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     NLP SERVICE (FastAPI + Python)                           │
│                        http://localhost:8000                                 │
│                                                                             │
│  ┌─────────────────────── NLP PIPELINE ───────────────────────────────┐     │
│  │                                                                     │     │
│  │  1. SCHEMA SAMPLING     →  schema_utils.py                         │     │
│  │     Sample N docs, flatten nested fields, detect types, cache      │     │
│  │                                                                     │     │
│  │  2. NL PARSING           →  llm_parser.py  OR  parser.py           │     │
│  │     Convert English to IR (Intermediate Representation)            │     │
│  │     • LLM mode: Google Gemini API                                  │     │
│  │     • Rule mode: Regex + keyword matching (1400+ lines)            │     │
│  │                                                                     │     │
│  │  3. IR VALIDATION        →  ir_validator.py                        │     │
│  │     Fuzzy field resolution, operator allow-list, limit caps        │     │
│  │                                                                     │     │
│  │  4. IR COMPILATION       →  ir_compiler.py                         │     │
│  │     Type-aware MongoDB query generation (regex, dates, ObjectId)   │     │
│  │                                                                     │     │
│  │  5. DB EXECUTION         →  db_executor.py                         │     │
│  │     Paginated find/aggregate with timeout protection               │     │
│  │                                                                     │     │
│  │  6. RESPONSE FORMATTING  →  response_formatter.py                  │     │
│  │     Paraphrased interpretation, pagination meta, index warnings    │     │
│  │                                                                     │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  Supporting modules:                                                        │
│    cluster_manager.py  — Connect, list DBs/collections                      │
│    config.py           — Env vars (MONGO_URI, GEMINI_API_KEY, etc.)         │
│    logger.py           — Centralized logging                                │
│    diagnose.py         — CLI diagnostic script                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │  PyMongo
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MONGODB CLUSTER                                     │
│              (Local, Atlas, or any MongoDB-compatible URI)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### NLP Pipeline Flow Diagram

```
  ┌──────────────────┐
  │  User types:     │
  │  "average salary │
  │   where dept is  │
  │   Engineering"   │
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐     ┌─────────────────────────────────────────┐
  │  1. SCHEMA       │────▶│ Sample 50 docs → flatten nested fields  │
  │     SAMPLING     │     │ Detect types: string, int, date, array  │
  │                  │     │ Cache result per collection              │
  │  schema_utils.py │     │ Output: allowed_fields, field_types     │
  └────────┬─────────┘     └─────────────────────────────────────────┘
           │
           ▼
  ┌──────────────────┐     ┌─────────────────────────────────────────┐
  │  2. NL PARSE     │────▶│ LLM (Gemini): schema-aware prompt       │
  │                  │     │   → JSON IR with conditions, agg, sort  │
  │  llm_parser.py   │     │ OR                                      │
  │  parser.py       │     │ Rule-based: keyword matching + regex    │
  │                  │     │   → Same JSON IR format                 │
  └────────┬─────────┘     └─────────────────────────────────────────┘
           │
           │  IR = { operation: "aggregate",
           │         conditions: [{field:"dept", operator:"eq", value:"Engineering"}],
           │         aggregation: {type:"avg", field:"salary"} }
           ▼
  ┌──────────────────┐     ┌─────────────────────────────────────────┐
  │  3. VALIDATE     │────▶│ Resolve "dept" → "department" (fuzzy)   │
  │                  │     │ Check operators against allow-list      │
  │  ir_validator.py │     │ Enforce limit ≤ 100                     │
  │                  │     │ "Did you mean?" suggestions for typos   │
  └────────┬─────────┘     └─────────────────────────────────────────┘
           │
           ▼
  ┌──────────────────┐     ┌─────────────────────────────────────────┐
  │  4. COMPILE      │────▶│ Build $match, $group, $sort stages     │
  │                  │     │ Type-aware: string→regex, date→datetime │
  │  ir_compiler.py  │     │ Array fields → partial match auto       │
  │                  │     │ ObjectId hex → BSON ObjectId             │
  └────────┬─────────┘     └─────────────────────────────────────────┘
           │
           │  mongo_query = { type: "aggregate",
           │    pipeline: [ {$match: {department: {$regex:"^Engineering$","$options":"i"}}},
           │                {$group: {_id: null, result: {$avg: "$salary"}}} ] }
           ▼
  ┌──────────────────┐     ┌─────────────────────────────────────────┐
  │  5. EXECUTE      │────▶│ PyMongo: collection.aggregate(pipeline) │
  │                  │     │ 5-second timeout protection             │
  │  db_executor.py  │     │ Pagination: skip/limit for find queries │
  │                  │     │ ObjectId → string serialization         │
  └────────┬─────────┘     └─────────────────────────────────────────┘
           │
           ▼
  ┌──────────────────┐     ┌─────────────────────────────────────────┐
  │  6. FORMAT       │────▶│ Human-readable interpretation string    │
  │                  │     │ Pagination metadata (page, total, etc.) │
  │  response_       │     │ Index warnings for unindexed fields     │
  │  formatter.py    │     │ Value hints on zero-result queries      │
  └────────┬─────────┘     └─────────────────────────────────────────┘
           │
           ▼
  ┌──────────────────┐
  │  JSON Response   │
  │  → API Gateway   │
  │  → React UI      │
  │  → Results Table │
  └──────────────────┘
```

---

## Tech Stack

| Layer            | Technology                      | Purpose                                    |
|------------------|---------------------------------|--------------------------------------------|
| **Frontend**     | React 19, Axios, CSS            | User interface with step-by-step wizard    |
| **API Gateway**  | Node.js, Express 5, Axios       | Request routing, validation, proxy layer   |
| **NLP Service**  | Python, FastAPI, Pydantic       | Core NLP pipeline and query processing     |
| **LLM Parser**   | Google Gemini API (`google-genai`) | AI-powered natural language understanding  |
| **Rule Parser**  | Python (regex, difflib)         | Fallback keyword-based NL parser           |
| **Database**     | MongoDB (any version), PyMongo  | Data storage and query execution           |

---

## Project Structure

```
nlp-mongodb-interface/
│
├── frontend/                   # React 19 single-page application
│   ├── package.json            # Dependencies: react, axios
│   ├── public/
│   │   └── index.html          # HTML shell
│   ├── src/
│   │   ├── App.js              # Main component — 4-step wizard UI
│   │   ├── api.js              # Axios HTTP client (all API calls)
│   │   ├── index.js            # React entry point
│   │   ├── index.css           # All styles (no CSS framework)
│   │   ├── App.css             # Additional styles
│   │   └── App.test.js         # Tests
│   └── build/                  # Production build output
│
├── api_gateway/                # Node.js Express proxy server
│   ├── package.json            # Dependencies: express, axios, cors, dotenv
│   ├── server.js               # Express app setup (port 5000)
│   ├── config/
│   │   └── nlpconfig.js        # NLP service URL configuration
│   ├── routes/
│   │   └── nlqRoutes.js        # Route definitions (/api/nlq/*)
│   └── controllers/
│       └── nlqController.js    # Request handlers (proxy to NLP service)
│
├── nlp_service/                # Python FastAPI NLP engine
│   ├── app.py                  # FastAPI app — endpoints & pipeline orchestration
│   ├── config.py               # Environment config (MONGO_URI, GEMINI_API_KEY)
│   ├── parser.py               # Rule-based NL parser (1431 lines)
│   ├── llm_parser.py           # LLM-based parser (Google Gemini, 570 lines)
│   ├── ir_validator.py         # IR validation & fuzzy field resolution
│   ├── ir_compiler.py          # IR → MongoDB query compiler (type-aware)
│   ├── db_executor.py          # Query execution with pagination & timeout
│   ├── schema_utils.py         # Schema sampling, flattening, caching, types
│   ├── cluster_manager.py      # Cluster connection, list DBs/collections
│   ├── response_formatter.py   # Response building, paraphrasing, warnings
│   ├── logger.py               # Centralized logging setup
│   ├── diagnose.py             # CLI diagnostic tool
│   ├── db.py                   # DEPRECATED (legacy, no active code)
│   └── requirements.txt        # Python dependencies
│
└── README.md                   # This file
```

---

## Detailed Component Breakdown

### 1. Frontend (React)

**Location:** `frontend/`

The frontend is a single-page React application that provides a **4-step wizard** for querying MongoDB:

| Step | Screen            | Description                                          |
|------|-------------------|------------------------------------------------------|
| 1    | **Connect**       | User pastes a MongoDB URI and connects to the cluster |
| 2    | **Select Database**| Displays all databases as clickable cards             |
| 3    | **Select Collection**| Shows collections with document counts              |
| 4    | **Query**         | Natural language input → results table with pagination|

**Key Files:**

- **`App.js`** — The entire UI in a single component. Manages state for connection, database/collection selection, query input/output, pagination, diagnostics, and cache clearing. Renders results in a dynamic HTML table.

- **`api.js`** — Axios HTTP client with functions:
  - `connectCluster(uri)` — POST to `/api/nlq/connect-cluster`
  - `getCollections(uri, db)` — POST to `/api/nlq/get-collections`
  - `runNLP(uri, db, col, query, page, pageSize)` — POST to `/api/nlq/run-nlp`
  - `diagnoseQuery(...)` — POST to `/api/nlq/diagnose`
  - `diagnoseSchema(...)` — POST to `/api/nlq/diagnose-schema`
  - `clearCache()` — POST to `/api/nlq/clear-cache`

**UI Features:**
- Step indicator breadcrumb (Connect → Database → Collection → Query)
- Back navigation between steps
- Loading states and error messages
- Paginated results table with Prev/Next controls
- Diagnostic panel (expandable trace of every pipeline step)
- Cache clear button
- Index information display

---

### 2. API Gateway (Node.js/Express)

**Location:** `api_gateway/`

A lightweight **proxy layer** that sits between the React frontend and the Python NLP service. All requests are forwarded to `http://localhost:8000` (configurable via `nlpconfig.js`).

**Why a separate gateway?**
- Decouples frontend from backend language/framework
- Provides a single entry point for all API calls
- Enables future additions (auth, rate limiting, logging, caching)
- Handles CORS centrally

**Routes (`/api/nlq/`):**

| Route                 | Method | Handler                | Purpose                          |
|-----------------------|--------|------------------------|----------------------------------|
| `/connect-cluster`    | POST   | `handleConnectCluster` | Connect to MongoDB cluster       |
| `/get-collections`    | POST   | `handleGetCollections` | List collections in a database   |
| `/run-nlp`            | POST   | `handleRunNLP`         | Execute NL query                 |
| `/run-nlp-stream`     | POST   | `handleRunNLPStream`   | Stream results (NDJSON)          |
| `/get-schema`         | POST   | `handleGetSchema`      | Get collection schema            |
| `/get-indexes`        | POST   | `handleGetIndexes`     | Get collection indexes           |
| `/diagnose`           | POST   | `handleDiagnose`       | Full pipeline diagnostic trace   |
| `/diagnose-schema`    | POST   | `handleDiagnoseSchema` | Schema flattening diagnostic     |
| `/clear-cache`        | POST   | `handleClearCache`     | Clear server-side schema cache   |
| `/llm-status`         | GET    | `handleLLMStatus`      | Check LLM parser availability    |

---

### 3. NLP Service (Python/FastAPI)

**Location:** `nlp_service/`

The core engine that processes natural language queries through a 6-stage pipeline.

#### Module Details

##### `app.py` — FastAPI Application (669 lines)
- Defines all REST endpoints
- Orchestrates the full NLP pipeline in `/run-nlp`
- Implements `/diagnose` endpoint for step-by-step pipeline tracing
- Provides streaming endpoint (`/run-nlp-stream`) for large result sets
- Schema cache cleared on startup/reload

##### `schema_utils.py` — Schema Sampling & Caching (309 lines)
- **Samples N documents** (default: 50) to discover all field paths
- **Flattens nested documents** into dot-notation (e.g., `address.city`)
- **Expands arrays of objects** — discovers sub-fields within array elements
- **Type detection** — classifies every field:
  - `string`, `int`, `float`, `bool`, `date`
  - `array_of_strings`, `array_of_numbers`, `array_of_objects`, `array_mixed`
  - `object`, `unknown`
- **In-memory caching** — schemas are cached per `(URI, database, collection)` key
- **Index inspection** — retrieves and parses collection indexes

##### `llm_parser.py` — LLM Parser (570 lines)
- Uses **Google Gemini API** (`gemini-2.0-flash` by default) for parsing
- Sends a schema-aware prompt with field names, types, and sample values
- LLM returns JSON IR directly — validated against allowed fields/operators
- **Auto-fixes** field name casing to match schema
- Falls back gracefully to rule-based parser on:
  - Missing API key
  - Missing `google-genai` SDK
  - LLM network/rate-limit errors
  - Invalid LLM response

##### `parser.py` — Rule-Based Parser (1431 lines)
- Comprehensive keyword-based NL parser
- Supports:
  - **Aggregation keywords**: count, average, sum, max, min
  - **Comparison operators**: greater, less, above, below, between, equals, contains
  - **Sort/limit**: "sorted by X ascending", "top 10", "first 5"
  - **Projections**: "show name and email where..."
  - **Temporal expressions**: "today", "last 7 days", "this month", "yesterday"
  - **Superlatives**: "highest salary", "cheapest product", "most recent"
  - **Fuzzy field matching**: handles typos using `difflib.SequenceMatcher`
  - **Negation**: "not", "isn't", "!=", "except", "excluding"
  - **Currency/number parsing**: strips `$`, `€`, `₹` symbols
  - **Category/context detection**: "in department X", "from city Y"

##### `ir_validator.py` — IR Validation (248 lines)
- **Field resolution** with 5-tier strategy:
  1. Exact match (case-insensitive)
  2. Space-to-dot conversion (`"options id"` → `"options.id"`)
  3. Dot-suffix/last-segment match (`"city"` → `"address.city"`)
  4. Multi-segment fuzzy (`"adress.city"` → `"address.city"`, threshold 0.8)
  5. Single-token fuzzy match (threshold 0.8)
- **Operator allow-list**: `eq, gt, lt, gte, lte, in, ne, exists, contains`
- **Hard limit cap**: maximum 100 results
- **"Did you mean?"** suggestions for unresolvable fields
- Resolves fields in conditions, aggregation, sort, and projection

##### `ir_compiler.py` — IR → MongoDB Compiler (274 lines)
- **Type-aware compilation**:
  - `string` + `eq` → case-insensitive anchored regex (`^value$`)
  - `array_of_strings` + `eq` → partial regex (un-anchored)
  - `int/float` → exact numeric match
  - `date` fields → auto-converts strings to `datetime` objects
  - `contains` → always un-anchored regex
  - ObjectId hex strings → BSON `ObjectId`
- Builds **`$match`** stages for filters
- Builds **`$group`** stages for aggregations (`$avg`, `$sum`, `$max`, `$min`, `$count`)
- Handles **`$sort`** with direction
- Supports **15+ date formats** including ISO, US, EU, and natural language

##### `db_executor.py` — Query Execution (203 lines)
- **Paginated execution**: `skip/limit` with configurable page size
- **Hard caps**: max 100 results per page, 5-second query timeout
- **Find queries**: `count_documents` + paginated `find` cursor
- **Aggregate queries**: runs pipeline with `maxTimeMS`
- **Streaming**: generator-based `stream_query()` for NDJSON responses
- **ObjectId serialization**: auto-converts `_id` to string

##### `response_formatter.py` — Response Building (146 lines)
- **Paraphrases IR** into human-readable interpretation
  (e.g., "Showing records where department is Engineering sorted by salary (desc)")
- **Cleans documents**: removes `_id`, sanitizes binary/datetime/ObjectId values
- **Pagination metadata**: page, page_size, total_results, result_count
- **Large dataset warning**: triggered when total_count > 100,000
- **Index information**: included in response when available

##### `cluster_manager.py` — Cluster Connection (53 lines)
- Tests MongoDB connectivity with `server_info()`
- Lists databases with `list_database_names()`
- Lists collections with **estimated** doc counts (avoids full scans)

##### `config.py` — Configuration (17 lines)
- Loads `.env` file via `dotenv`
- Exposes: `MONGO_URI`, `DATABASE_NAME`, `COLLECTION_NAME`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `PARSER_MODE`

##### `diagnose.py` — CLI Diagnostic Script (264 lines)
- Command-line tool for full pipeline debugging
- Usage: `python diagnose.py <mongo_uri> <database> <collection> "<query>"`
- Prints color-coded step-by-step trace of schema → parse → validate → compile → execute

---

## NLP Pipeline — End-to-End Workflow

When a user submits a natural language query, the following 8-step pipeline executes:

### Step 1: Schema Sampling (`schema_utils.py`)
```
Input:  mongo_uri, database_name, collection_name
Output: allowed_fields[], numeric_fields[], field_types{}
```
- Samples 50 documents from the collection
- Recursively flattens nested objects into dot-notation paths
- Expands array-of-objects to discover sub-field paths
- Detects field types (string, int, date, array_of_strings, etc.)
- Caches results in memory (cleared on server restart or manual clear)

### Step 2: Natural Language Parsing (`llm_parser.py` / `parser.py`)
```
Input:  query string, allowed_fields, numeric_fields, field_types
Output: Intermediate Representation (IR) JSON
```
- **Auto/LLM mode**: Sends query + schema to Google Gemini → receives JSON IR
- **Rule mode**: Pattern-matches keywords, extracts fields/values/operators
- **Auto mode**: Tries LLM first, falls back to rule-based on failure

### Step 3: IR Validation (`ir_validator.py`)
```
Input:  raw IR, allowed_fields
Output: validated IR (with resolved field names)
```
- Resolves every field reference against the schema
- Fuzzy-matches typos (e.g., "nam" → "name")
- Maps short names to full paths (e.g., "city" → "address.city")
- Validates operators and enforces limit caps

### Step 4: IR Compilation (`ir_compiler.py`)
```
Input:  validated IR, field_types
Output: MongoDB query dict (filter/pipeline, sort, limit)
```
- Dynamically selects MongoDB operators based on field types
- Converts date strings to `datetime` objects
- Builds `$match`, `$group`, `$sort` stages for aggregation pipelines

### Step 5: Projection Extraction
- Extracts requested fields from the validated IR
- Builds MongoDB projection dict (`{field: 1}`)

### Step 6: Index Inspection (`schema_utils.py`)
- Retrieves collection indexes (non-blocking)
- Identifies unindexed fields used in the query

### Step 7: Query Execution (`db_executor.py`)
```
Input:  mongo_query, page, page_size, projection_fields
Output: {data[], total_count, page, page_size}
```
- Executes `find()` or `aggregate()` via PyMongo
- Applies pagination (skip/limit) and projection
- 5-second timeout protection

### Step 8: Response Formatting (`response_formatter.py`)
```
Output: {interpretation, data[], total_results, page, indexes[], warning?}
```
- Generates human-readable interpretation of the query
- Cleans documents (removes `_id`, serializes non-JSON types)
- Attaches pagination metadata and index warnings
- On zero results: provides sample values as hints

---

## API Endpoints Reference

### NLP Service (FastAPI — Port 8000)

| Endpoint             | Method | Description                                      |
|----------------------|--------|--------------------------------------------------|
| `/connect-cluster`   | POST   | Test connection, return list of databases         |
| `/get-collections`   | POST   | List collections with doc counts for a database   |
| `/get-schema`        | POST   | Return sampled & flattened schema for a collection|
| `/get-indexes`       | POST   | Return index information for a collection         |
| `/run-nlp`           | POST   | **Main endpoint** — full NLP pipeline execution   |
| `/run-nlp-stream`    | POST   | Streaming version (NDJSON, one doc per line)       |
| `/diagnose`          | POST   | Full pipeline diagnostic trace (all steps)         |
| `/diagnose-schema`   | POST   | Schema flattening diagnostic                       |
| `/clear-cache`       | POST   | Clear in-memory schema cache                       |
| `/llm-status`        | GET    | Check LLM parser configuration status              |
| `/health`            | GET    | Health check                                       |

### API Gateway (Express — Port 5000)

All routes are prefixed with `/api/nlq/` and proxy directly to the NLP service.

---

## Intermediate Representation (IR) Format

The IR is the common data structure shared between the parser, validator, compiler, and response formatter:

```json
{
  "operation": "find | aggregate",
  "conditions": [
    {
      "field": "department",
      "operator": "eq | gt | lt | gte | lte | ne | in | exists | contains",
      "value": "Engineering"
    }
  ],
  "aggregation": {
    "type": "count | avg | sum | max | min",
    "field": "salary"
  },
  "sort": {
    "field": "salary",
    "direction": "asc | desc"
  },
  "limit": 10,
  "projection": ["name", "email", "salary"]
}
```

---

## Parser Modes

Configured via the `PARSER_MODE` environment variable:

| Mode     | Behavior                                                  |
|----------|-----------------------------------------------------------|
| `auto`   | **Default.** Try LLM first → fall back to rule-based     |
| `llm`    | LLM only (fails if Gemini unavailable)                    |
| `rule`   | Rule-based only (no LLM calls)                           |

---

## Key Features

| Feature                        | Description                                                      |
|--------------------------------|------------------------------------------------------------------|
| **Dual Parser System**         | AI (Gemini) + rule-based fallback for 100% availability          |
| **Schema-Aware Parsing**       | Parsers receive field names and types for accurate translation    |
| **Fuzzy Field Resolution**     | Handles typos, partial names, dot-notation shortcuts              |
| **Type-Aware Compilation**     | Auto-selects MongoDB operators based on field data types          |
| **Nested Field Support**       | Full dot-notation support for deeply nested documents             |
| **Array-of-Objects Expansion** | Discovers and queries fields within array elements                |
| **Pagination**                 | Configurable page size with navigation (max 100 per page)        |
| **Query Timeout Protection**   | 5-second hard cap prevents runaway queries                       |
| **Streaming Responses**        | NDJSON streaming for large result sets                            |
| **In-Memory Schema Cache**     | Fast repeated queries; manual cache clearing available            |
| **Index Awareness**            | Warns about unindexed fields; shows collection indexes            |
| **Value Hints**                | On zero results, shows actual field values from the collection    |
| **Pipeline Diagnostics**       | Step-by-step trace of the entire NLP pipeline for debugging       |
| **Date/Time Handling**         | Supports 15+ date formats, temporal expressions, whole-day ranges |
| **ObjectId Support**           | Auto-detects 24-char hex strings and converts to BSON ObjectId    |
| **Projection Support**         | Users can request specific fields ("show name and email")         |
| **Human-Readable Response**    | Every query returns a plain English interpretation                |

---

## Installation & Setup

### Prerequisites
- **Python 3.9+**
- **Node.js 18+**
- **MongoDB** (local or Atlas cluster)
- **Google Gemini API Key** (optional, for LLM parser)

### 1. Clone the Repository
```bash
git clone https://github.com/AbhayShinde16325/nlp-mongodb-interface.git
cd nlp-mongodb-interface
```

### 2. Set Up the NLP Service (Python)
```bash
cd nlp_service
pip install -r requirements.txt
```

Create a `.env` file in `nlp_service/`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
PARSER_MODE=auto
```

Start the service:
```bash
uvicorn app:app --reload --port 8000
```

### 3. Set Up the API Gateway (Node.js)
```bash
cd api_gateway
npm install
```

Start the gateway:
```bash
node server.js
# or
npm start
```

### 4. Set Up the Frontend (React)
```bash
cd frontend
npm install
npm start
```

### 5. Access the Application
Open **http://localhost:3000** in your browser.

---

## Environment Variables

| Variable          | Default              | Description                                    |
|-------------------|----------------------|------------------------------------------------|
| `GEMINI_API_KEY`  | *(empty)*            | Google Gemini API key for LLM parser           |
| `GEMINI_MODEL`    | `gemini-2.0-flash`   | Gemini model name                              |
| `PARSER_MODE`     | `auto`               | Parser strategy: `auto`, `llm`, or `rule`      |
| `MONGO_URI`       | *(optional)*         | Default MongoDB URI (overridden by UI input)   |
| `DATABASE_NAME`   | *(optional)*         | Default database name                          |
| `COLLECTION_NAME` | *(optional)*         | Default collection name                        |
| `PORT`            | `5000`               | API Gateway port                               |

---

## Usage Examples

### Natural Language Queries

| Query                                         | What It Does                                      |
|-----------------------------------------------|---------------------------------------------------|
| `show all`                                    | Returns all documents (paginated)                 |
| `show name, email, salary`                    | Projection — only specified fields                |
| `show employees where city is Mumbai`         | Filter by field value                             |
| `count employees where department is HR`      | Aggregation — count with filter                   |
| `average salary where department is Engineering` | Aggregation — average with filter              |
| `top 5 products sorted by price descending`   | Sort + limit                                      |
| `show records where age greater than 30`      | Comparison operator                               |
| `show users who joined after 2023-01-01`      | Date comparison                                   |
| `show records where name contains John`       | Partial string match                              |
| `show records where status is not active`     | Negation                                          |
| `show records where tags is Python`           | Array field search                                |
| `highest salary in Engineering`               | Superlative → max aggregation with filter         |
| `show records from last 7 days`               | Temporal expression                               |

---

## Diagnostic Tools

### In-Browser Diagnostics
Click the **🔍 Diagnose** button after entering a query to see a step-by-step trace:
- **Step 0**: Raw data inspection (sample document fields)
- **Step 1**: Schema detection (fields, types, counts)
- **Step 2**: Parser output (raw IR, which parser was used)
- **Step 3**: Field resolution trace (raw → resolved, matches/misses)
- **Step 4**: Validation result (pass/fail)
- **Step 5**: Compiled MongoDB query (filter, sort, limit, pipeline)
- **Step 6**: Execution preview (total count, sample docs)
- **Step 7**: Index analysis (indexed vs. unindexed fields)

### CLI Diagnostic Script
```bash
cd nlp_service
python diagnose.py "mongodb://localhost:27017" mydb mycollection "show all users"
```

### LLM Status Check
```
GET http://localhost:8000/llm-status
```
Returns whether the LLM parser is configured, the API key is set, and the SDK is installed.

---

## Configuration

### Schema Sampling
- Default sample size: **50 documents**
- Cache is in-memory, cleared on server restart
- Manual clear: POST `/clear-cache` or click 🗑️ in the UI

### Query Limits
- Max results per page: **100**
- Default page size: **20**
- Query timeout: **5 seconds**
- Server selection timeout: **5 seconds**

### Supported Operators
`eq`, `gt`, `lt`, `gte`, `lte`, `ne`, `in`, `exists`, `contains`

### Supported Aggregations
`count`, `avg`, `sum`, `max`, `min`

---

## License

ISC

---

*Built with ❤️ for making MongoDB accessible to everyone through natural language.*
