const axios = require("axios");
const { NLP_SERVICE_URL } = require("../config/nlpconfig");

// POST /connect-cluster — forward cluster URI, receive database list
const handleConnectCluster = async (req, res) => {
    try {
        const { mongo_uri } = req.body;
        if (!mongo_uri) {
            return res.status(400).json({ error: "MongoDB URI is required" });
        }
        const response = await axios.post(`${NLP_SERVICE_URL}/connect-cluster`, { mongo_uri });
        return res.json(response.data);
    } catch (error) {
        console.error("Connect Cluster Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /get-collections — forward URI + db name, receive collection list
const handleGetCollections = async (req, res) => {
    try {
        const { mongo_uri, database_name } = req.body;
        if (!mongo_uri || !database_name) {
            return res.status(400).json({ error: "mongo_uri and database_name are required" });
        }
        const response = await axios.post(`${NLP_SERVICE_URL}/get-collections`, {
            mongo_uri,
            database_name,
        });
        return res.json(response.data);
    } catch (error) {
        console.error("Get Collections Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /run-nlp — forward URI + db + collection + NL query + pagination, receive results
const handleRunNLP = async (req, res) => {
    try {
        const { mongo_uri, database_name, collection_name, query, page, page_size, history, user_email } = req.body;
        if (!mongo_uri || !database_name || !collection_name || !query) {
            return res.status(400).json({
                error: "mongo_uri, database_name, collection_name, and query are required",
            });
        }
        const payload = {
            mongo_uri,
            database_name,
            collection_name,
            query,
        };
        if (page !== undefined) payload.page = page;
        if (page_size !== undefined) payload.page_size = page_size;
        if (history && Array.isArray(history) && history.length > 0) payload.history = history;
        if (user_email) payload.user_email = user_email;

        const response = await axios.post(`${NLP_SERVICE_URL}/run-nlp`, payload, { timeout: 60000 });
        return res.json(response.data);
    } catch (error) {
        console.error("NLP Service Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /run-nlp-stream — streaming endpoint (proxy NDJSON)
const handleRunNLPStream = async (req, res) => {
    try {
        const { mongo_uri, database_name, collection_name, query, page_size } = req.body;
        if (!mongo_uri || !database_name || !collection_name || !query) {
            return res.status(400).json({
                error: "mongo_uri, database_name, collection_name, and query are required",
            });
        }
        const payload = { mongo_uri, database_name, collection_name, query };
        if (page_size !== undefined) payload.page_size = page_size;

        const response = await axios.post(`${NLP_SERVICE_URL}/run-nlp-stream`, payload, {
            responseType: "stream",
        });

        res.setHeader("Content-Type", "application/x-ndjson");
        response.data.pipe(res);
    } catch (error) {
        console.error("NLP Stream Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /get-schema — get schema for a collection
const handleGetSchema = async (req, res) => {
    try {
        const { mongo_uri, database_name, collection_name } = req.body;
        if (!mongo_uri || !database_name || !collection_name) {
            return res.status(400).json({
                error: "mongo_uri, database_name, and collection_name are required",
            });
        }
        const response = await axios.post(`${NLP_SERVICE_URL}/get-schema`, {
            mongo_uri,
            database_name,
            collection_name,
        });
        return res.json(response.data);
    } catch (error) {
        console.error("Get Schema Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /get-indexes — get index info for a collection
const handleGetIndexes = async (req, res) => {
    try {
        const { mongo_uri, database_name, collection_name } = req.body;
        if (!mongo_uri || !database_name || !collection_name) {
            return res.status(400).json({
                error: "mongo_uri, database_name, and collection_name are required",
            });
        }
        const response = await axios.post(`${NLP_SERVICE_URL}/get-indexes`, {
            mongo_uri,
            database_name,
            collection_name,
        });
        return res.json(response.data);
    } catch (error) {
        console.error("Get Indexes Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /diagnose — full pipeline diagnostic trace
const handleDiagnose = async (req, res) => {
    try {
        const { mongo_uri, database_name, collection_name, query, history, user_email } = req.body;
        if (!mongo_uri || !database_name || !collection_name || !query) {
            return res.status(400).json({
                error: "mongo_uri, database_name, collection_name, and query are required",
            });
        }
        const payload = { mongo_uri, database_name, collection_name, query };
        if (history && Array.isArray(history) && history.length > 0) payload.history = history;
        if (user_email) payload.user_email = user_email;

        const response = await axios.post(`${NLP_SERVICE_URL}/diagnose`, payload, { timeout: 60000 });
        return res.json(response.data);
    } catch (error) {
        console.error("Diagnose Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /diagnose-schema — schema flattening diagnostic
const handleDiagnoseSchema = async (req, res) => {
    try {
        const { mongo_uri, database_name, collection_name } = req.body;
        if (!mongo_uri || !database_name || !collection_name) {
            return res.status(400).json({
                error: "mongo_uri, database_name, and collection_name are required",
            });
        }
        const response = await axios.post(`${NLP_SERVICE_URL}/diagnose-schema`, {
            mongo_uri, database_name, collection_name, query: "diagnose",
        }, { timeout: 30000 });
        return res.json(response.data);
    } catch (error) {
        console.error("Diagnose Schema Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /clear-cache — clear schema cache
const handleClearCache = async (req, res) => {
    try {
        const response = await axios.post(`${NLP_SERVICE_URL}/clear-cache`);
        return res.json(response.data);
    } catch (error) {
        console.error("Clear Cache Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// GET /llm-status — check if LLM parser is configured
const handleLLMStatus = async (req, res) => {
    try {
        const response = await axios.get(`${NLP_SERVICE_URL}/llm-status`);
        return res.json(response.data);
    } catch (error) {
        console.error("LLM Status Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /mutation-estimate — count documents matching a filter (no LLM)
const handleMutationEstimate = async (req, res) => {
    try {
        const { mongo_uri, database_name, collection_name, filter } = req.body;
        if (!mongo_uri || !database_name || !collection_name) {
            return res.status(400).json({
                error: "mongo_uri, database_name, and collection_name are required",
            });
        }
        const payload = { mongo_uri, database_name, collection_name, filter: filter || {} };
        const response = await axios.post(`${NLP_SERVICE_URL}/mutation-estimate`, payload, { timeout: 30000 });
        return res.json(response.data);
    } catch (error) {
        console.error("Mutation Estimate Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /mutation-preview — parse NL mutation, return preview without executing
const handleMutationPreview = async (req, res) => {
    try {
        const { mongo_uri, database_name, collection_name, query, history } = req.body;
        if (!mongo_uri || !database_name || !collection_name || !query) {
            return res.status(400).json({
                error: "mongo_uri, database_name, collection_name, and query are required",
            });
        }
        const payload = { mongo_uri, database_name, collection_name, query };
        if (history && Array.isArray(history) && history.length > 0) payload.history = history;

        const response = await axios.post(`${NLP_SERVICE_URL}/mutation-preview`, payload, { timeout: 60000 });
        return res.json(response.data);
    } catch (error) {
        console.error("Mutation Preview Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// POST /mutation-commit — execute a previously previewed mutation
const handleMutationCommit = async (req, res) => {
    try {
        const { mongo_uri, database_name, collection_name, mutation, user_email } = req.body;
        if (!mongo_uri || !database_name || !collection_name || !mutation) {
            return res.status(400).json({
                error: "mongo_uri, database_name, collection_name, and mutation are required",
            });
        }
        const response = await axios.post(`${NLP_SERVICE_URL}/mutation-commit`, {
            mongo_uri,
            database_name,
            collection_name,
            mutation,
            ...(user_email ? { user_email } : {}),
        }, { timeout: 60000 });
        return res.json(response.data);
    } catch (error) {
        console.error("Mutation Commit Error:", error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

// ==================== ANALYTICS / DASHBOARD ====================

// Generic analytics proxy helper
const proxyAnalytics = (endpoint) => async (req, res) => {
    try {
        const { mongo_uri, database_name, user_email, year, month, day, days, hours, minutes, granularity } = req.body;
        if (!mongo_uri || !database_name) {
            return res.status(400).json({ error: "mongo_uri and database_name are required" });
        }
        const payload = { mongo_uri, database_name };
        if (user_email) payload.user_email = user_email;
        if (year !== undefined) payload.year = year;
        if (month !== undefined) payload.month = month;
        if (day !== undefined) payload.day = day;
        if (days !== undefined) payload.days = days;
        if (hours !== undefined) payload.hours = hours;
        if (minutes !== undefined) payload.minutes = minutes;
        if (granularity) payload.granularity = granularity;

        const response = await axios.post(`${NLP_SERVICE_URL}${endpoint}`, payload, { timeout: 30000 });
        return res.json(response.data);
    } catch (error) {
        console.error(`Analytics ${endpoint} Error:`, error.message);
        if (error.response) {
            return res.status(error.response.status).json(error.response.data);
        }
        return res.status(500).json({ error: "Internal server error" });
    }
};

const handleCommitTimeline = proxyAnalytics("/analytics/commit-timeline");
const handleActivityStats = proxyAnalytics("/analytics/stats");
const handleDiagnosisMonthly = proxyAnalytics("/analytics/diagnosis-monthly");

module.exports = {
    handleConnectCluster,
    handleGetCollections,
    handleRunNLP,
    handleRunNLPStream,
    handleGetSchema,
    handleGetIndexes,
    handleDiagnose,
    handleDiagnoseSchema,
    handleClearCache,
    handleLLMStatus,
    handleMutationEstimate,
    handleMutationPreview,
    handleMutationCommit,
    handleCommitTimeline,
    handleActivityStats,
    handleDiagnosisMonthly,
};
