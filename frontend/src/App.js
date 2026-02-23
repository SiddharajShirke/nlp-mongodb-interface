import React, { useState } from "react";
import { connectCluster, getCollections, runNLP, diagnoseQuery, diagnoseSchema, clearCache } from "./api";
import "./index.css";

function App() {
  // Connection
  const [mongoUri, setMongoUri] = useState("");
  const [step, setStep] = useState(1);

  // Databases
  const [databases, setDatabases] = useState([]);
  const [totalDatabases, setTotalDatabases] = useState(0);
  const [selectedDb, setSelectedDb] = useState("");

  // Collections
  const [collections, setCollections] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState("");

  // Query
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState(null);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(20);

  // UI
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [diagResult, setDiagResult] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);

  /* ---------- handlers ---------- */

  const handleConnect = async () => {
    if (!mongoUri.trim() || loading) return;
    try {
      setLoading(true);
      setError(null);
      const data = await connectCluster(mongoUri);
      setDatabases(data.databases);
      setTotalDatabases(data.total_databases);
      setStep(2);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Failed to connect to cluster. Check your URI.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDatabase = async (dbName) => {
    try {
      setLoading(true);
      setError(null);
      setSelectedDb(dbName);
      const data = await getCollections(mongoUri, dbName);
      setCollections(data.collections);
      setStep(3);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Failed to load collections.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCollection = (colName) => {
    setSelectedCollection(colName);
    setResponse(null);
    setQuery("");
    setCurrentPage(1);
    setStep(4);
  };

  const handleRunQuery = async (page = 1) => {
    if (!query.trim() || loading) return;
    try {
      setLoading(true);
      setError(null);
      setResponse(null);
      const data = await runNLP(mongoUri, selectedDb, selectedCollection, query, page, pageSize);
      setResponse(data);
      setCurrentPage(page);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Failed to process query. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (newPage) => {
    if (newPage < 1) return;
    handleRunQuery(newPage);
  };

  const handleDiagnose = async () => {
    if (!query.trim() || diagLoading) return;
    try {
      setDiagLoading(true);
      setDiagResult(null);
      setError(null);
      const data = await diagnoseQuery(mongoUri, selectedDb, selectedCollection, query);
      setDiagResult(data);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Diagnosis failed.");
    } finally {
      setDiagLoading(false);
    }
  };

  const handleClearCache = async () => {
    try {
      await clearCache();
      setError(null);
      alert("Schema cache cleared! Next query will use fresh schema.");
    } catch (err) {
      setError("Failed to clear cache.");
    }
  };

  const handleBack = () => {
    setError(null);
    if (step === 2) {
      setStep(1);
      setDatabases([]);
      setSelectedDb("");
    } else if (step === 3) {
      setStep(2);
      setCollections([]);
      setSelectedCollection("");
    } else if (step === 4) {
      setStep(3);
      setSelectedCollection("");
      setResponse(null);
      setQuery("");
      setCurrentPage(1);
    }
  };

  /* ---------- compute pagination ---------- */
  const totalResults = response?.total_results || 0;
  const totalPages = Math.max(1, Math.ceil(totalResults / pageSize));

  return (
    <div className="app-container">
      <div className="title">Natural Language MongoDB Interface</div>

      {/* Step indicator */}
      <div className="step-indicator">
        <span className={step >= 1 ? "step active" : "step"}>1. Connect</span>
        <span className="step-arrow">&rarr;</span>
        <span className={step >= 2 ? "step active" : "step"}>2. Database</span>
        <span className="step-arrow">&rarr;</span>
        <span className={step >= 3 ? "step active" : "step"}>3. Collection</span>
        <span className="step-arrow">&rarr;</span>
        <span className={step >= 4 ? "step active" : "step"}>4. Query</span>
      </div>

      {step > 1 && (
        <button className="back-btn" onClick={handleBack}>
          &larr; Back
        </button>
      )}

      {error && <div className="error-text">{error}</div>}

      {/* -------- STEP 1: Paste URI -------- */}
      {step === 1 && (
        <div className="step-content">
          <div className="subtitle">
            Paste your MongoDB cluster URI to get started
          </div>
          <div className="input-row">
            <input
              type="text"
              value={mongoUri}
              onChange={(e) => setMongoUri(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleConnect()}
              placeholder="mongodb+srv://user:pass@cluster.mongodb.net"
              className="input-field"
            />
            <button
              onClick={handleConnect}
              disabled={loading}
              className="submit-btn"
            >
              {loading ? "Connecting..." : "Connect"}
            </button>
          </div>
        </div>
      )}

      {/* -------- STEP 2: Select Database -------- */}
      {step === 2 && (
        <div className="step-content">
          <div className="info-badge">
            {totalDatabases} database{totalDatabases !== 1 ? "s" : ""} found
          </div>
          <div className="subtitle">Select a database to explore</div>
          <div className="card-grid">
            {databases.map((db) => (
              <div
                key={db}
                className="card"
                onClick={() => handleSelectDatabase(db)}
              >
                <div className="card-title">{db}</div>
                <div className="card-action">Connect &rarr;</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* -------- STEP 3: Select Collection -------- */}
      {step === 3 && (
        <div className="step-content">
          <div className="info-badge">
            {selectedDb} &mdash; {collections.length} collection
            {collections.length !== 1 ? "s" : ""}
          </div>
          <div className="subtitle">Select a collection to query</div>
          <div className="card-grid">
            {collections.map((col) => (
              <div
                key={col.name}
                className="card"
                onClick={() => handleSelectCollection(col.name)}
              >
                <div className="card-title">{col.name}</div>
                <div className="card-subtitle">
                  {col.document_count.toLocaleString()} documents
                </div>
                <div className="card-action">Select &rarr;</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* -------- STEP 4: NLP Query -------- */}
      {step === 4 && (
        <div className="step-content">
          <div className="info-badge">
            {selectedDb} &rarr; {selectedCollection}
          </div>
          <div className="subtitle">
            Ask a question in plain English about your data
          </div>
          <div className="input-row">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleRunQuery(1)}
              placeholder='Try: "show all", "average salary", "count users in Mumbai"'
              className="input-field"
            />
            <button
              onClick={() => handleRunQuery(1)}
              disabled={loading}
              className="submit-btn"
            >
              {loading ? "Processing..." : "Run Query"}
            </button>
            <button
              onClick={handleDiagnose}
              disabled={diagLoading || !query.trim()}
              className="submit-btn"
              style={{ backgroundColor: "#6c5ce7", marginLeft: "8px" }}
              title="Run full pipeline diagnosis to see every step"
            >
              {diagLoading ? "Diagnosing..." : "🔍 Diagnose"}
            </button>
            <button
              onClick={handleClearCache}
              className="submit-btn"
              style={{ backgroundColor: "#e17055", marginLeft: "8px", fontSize: "0.85rem" }}
              title="Clear schema cache — forces re-sampling on next query"
            >
              🗑️ Clear Cache
            </button>
          </div>

          {/* Diagnostic Results Panel */}
          {diagResult && (
            <details className="debug-panel" open>
              <summary style={{ cursor: "pointer", fontWeight: "bold", color: "#6c5ce7" }}>
                🔍 Pipeline Diagnosis Trace
              </summary>
              <div style={{ fontSize: "0.85rem", lineHeight: "1.6" }}>
                {diagResult.steps?.["0_raw_sample"] && (
                  <div style={{ marginBottom: "10px", padding: "8px", background: "#fef9e7", borderRadius: "6px", border: "1px solid #f0e68c" }}>
                    <strong>Step 0 — Raw Data Inspection:</strong>{" "}
                    <span>📦 {diagResult.steps["0_raw_sample"].total_documents} total documents in collection</span>
                    {diagResult.steps["0_raw_sample"].sample_fields ? (
                      <div style={{ marginTop: "4px" }}>
                        <em>Sample document fields:</em>
                        <pre style={{ fontSize: "0.8rem", background: "#fff", padding: "6px", borderRadius: "4px", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                          {JSON.stringify(diagResult.steps["0_raw_sample"].sample_fields, null, 2)}
                        </pre>
                      </div>
                    ) : (
                      <span style={{ color: "red" }}> — Collection is empty!</span>
                    )}
                  </div>
                )}

                {diagResult.steps?.["1_schema"] && (
                  <div style={{ marginBottom: "8px" }}>
                    <strong>Step 1 — Schema:</strong>{" "}
                    {diagResult.steps["1_schema"].status === "ok" ? (
                      <span style={{ color: "green" }}>
                        ✅ {diagResult.steps["1_schema"].field_count} fields detected
                        <br />
                        <code style={{ fontSize: "0.8rem" }}>
                          {JSON.stringify(diagResult.steps["1_schema"].allowed_fields)}
                        </code>
                      </span>
                    ) : (
                      <span style={{ color: "red" }}>❌ {diagResult.steps["1_schema"].error}</span>
                    )}
                  </div>
                )}

                {diagResult.steps?.["2_parse"] && (
                  <div style={{ marginBottom: "8px" }}>
                    <strong>Step 2 — Parser (raw IR):</strong>{" "}
                    {diagResult.steps["2_parse"].status === "ok" ? (
                      <span style={{ color: "green" }}>
                        ✅ op={diagResult.steps["2_parse"].raw_ir?.operation}
                        <pre style={{ fontSize: "0.8rem", background: "#f5f5f5", padding: "6px", borderRadius: "4px" }}>
                          {JSON.stringify(diagResult.steps["2_parse"].raw_ir, null, 2)}
                        </pre>
                      </span>
                    ) : (
                      <span style={{ color: "red" }}>❌ {diagResult.steps["2_parse"].error}</span>
                    )}
                  </div>
                )}

                {diagResult.steps?.["3_resolve"] && (
                  <div style={{ marginBottom: "8px" }}>
                    <strong>Step 3 — Field Resolution:</strong>
                    <ul style={{ margin: "4px 0", paddingLeft: "20px" }}>
                      {diagResult.steps["3_resolve"].map((r, i) => (
                        <li key={i} style={{ color: r.matched ? "green" : "red" }}>
                          {r.matched
                            ? r.raw_field !== r.resolved_field
                              ? `✅ "${r.raw_field}" → "${r.resolved_field}"`
                              : `✅ "${r.raw_field}" (exact match)`
                            : `❌ "${r.raw_field}" — NOT FOUND in schema`}
                          {r.context ? ` [${r.context}]` : ""}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {diagResult.steps?.["4_validate"] && (
                  <div style={{ marginBottom: "8px" }}>
                    <strong>Step 4 — Validation:</strong>{" "}
                    {diagResult.steps["4_validate"].status === "ok" ? (
                      <span style={{ color: "green" }}>✅ Passed</span>
                    ) : (
                      <span style={{ color: "red" }}>❌ {diagResult.steps["4_validate"].error}</span>
                    )}
                  </div>
                )}

                {diagResult.steps?.["5_compile"] && (
                  <div style={{ marginBottom: "8px" }}>
                    <strong>Step 5 — MongoDB Query:</strong>
                    <pre style={{ fontSize: "0.8rem", background: "#f5f5f5", padding: "6px", borderRadius: "4px" }}>
                      type: {diagResult.steps["5_compile"].type}{"\n"}
                      filter: {diagResult.steps["5_compile"].filter}{"\n"}
                      sort: {diagResult.steps["5_compile"].sort}{"\n"}
                      limit: {String(diagResult.steps["5_compile"].limit)}
                    </pre>
                  </div>
                )}

                {diagResult.steps?.["6_execute_preview"] && (
                  <div style={{ marginBottom: "8px" }}>
                    <strong>Step 6 — Execution:</strong>{" "}
                    {diagResult.steps["6_execute_preview"].total_count > 0 ? (
                      <span style={{ color: "green" }}>
                        ✅ {diagResult.steps["6_execute_preview"].total_count} documents matched
                      </span>
                    ) : (
                      <span style={{ color: "red" }}>
                        ❌ 0 documents matched — check the filter above
                      </span>
                    )}
                  </div>
                )}

                {diagResult.steps?.["7_index_info"]?.unindexed_fields?.length > 0 && (
                  <div style={{ marginBottom: "8px" }}>
                    <strong>Step 7 — Indexes:</strong>{" "}
                    <span style={{ color: "orange" }}>
                      ⚠ Unindexed: {diagResult.steps["7_index_info"].unindexed_fields.join(", ")}
                    </span>
                  </div>
                )}
              </div>
            </details>
          )}

          {response && (
            <>
              <div className="interpretation">
                <strong>Interpretation:</strong> {response.interpretation}
              </div>

              {/* Debug panel: show compiled query details */}
              {response.interpreted_ir && (
                <details className="debug-panel">
                  <summary>Debug: Parsed IR &amp; Mongo Query</summary>
                  <pre>{JSON.stringify(response.interpreted_ir, null, 2)}</pre>
                </details>
              )}

              {response.warning && (
                <div className="warning-text">
                  &#9888; {response.warning}
                </div>
              )}

              {response.result !== undefined && response.interpreted_ir?.operation === "aggregate" && (
                <div className="result-number">Result: {response.result}</div>
              )}

              {response.total_results !== undefined && response.data && (
                <div className="result-count">
                  Showing {response.result_count} of{" "}
                  {response.total_results.toLocaleString()} total document
                  {response.total_results !== 1 ? "s" : ""} (page{" "}
                  {response.page} of {totalPages})
                </div>
              )}

              {response.data && response.data.length === 0 && (
                <div className="no-results">
                  No documents matched your query. Check field names and values.
                  {response.interpreted_ir?.conditions?.length > 0 && (
                    <span>
                      {" "}Filter used:{" "}
                      {response.interpreted_ir.conditions.map(
                        (c) => `${c.field} ${c.operator} ${c.value}`
                      ).join(", ")}
                    </span>
                  )}
                  {response.value_hint && (
                    <div style={{ marginTop: "8px", padding: "8px", background: "#fef9e7", borderRadius: "4px", border: "1px solid #f0e68c", fontSize: "0.85rem" }}>
                      💡 <strong>Hint:</strong> {response.value_hint}
                      <br />
                      <em>Try: "show records where [field] contains [part of value]"</em>
                    </div>
                  )}
                </div>
              )}

              {response.data && response.data.length > 0 && (
                <>
                  <table className="result-table">
                    <thead>
                      <tr>
                        {Object.keys(response.data[0]).map((key) => (
                          <th key={key}>{key}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {response.data.map((row, idx) => (
                        <tr key={idx}>
                          {Object.values(row).map((val, i) => (
                            <td key={i}>
                              {typeof val === "object"
                                ? JSON.stringify(val)
                                : String(val)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Pagination controls */}
                  {totalPages > 1 && (
                    <div className="pagination-controls">
                      <button
                        disabled={currentPage <= 1 || loading}
                        onClick={() => handlePageChange(currentPage - 1)}
                        className="page-btn"
                      >
                        &larr; Prev
                      </button>
                      <span className="page-info">
                        Page {currentPage} of {totalPages}
                      </span>
                      <button
                        disabled={currentPage >= totalPages || loading}
                        onClick={() => handlePageChange(currentPage + 1)}
                        className="page-btn"
                      >
                        Next &rarr;
                      </button>
                    </div>
                  )}
                </>
              )}

              {response.indexes && response.indexes.length > 0 && (
                <details className="index-info">
                  <summary>
                    Indexes ({response.indexes.length})
                  </summary>
                  <ul>
                    {response.indexes.map((idx, i) => (
                      <li key={i}>
                        <strong>{idx.name}</strong>
                        {idx.unique ? " (unique)" : ""}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </div>
      )}

      {loading && step > 1 && <div className="loading-bar" />}
    </div>
  );
}

export default App;
