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
        const { mongo_uri, database_name, collection_name, query, page, page_size } = req.body;
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

        const response = await axios.post(`${NLP_SERVICE_URL}/run-nlp`, payload);
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
        const { mongo_uri, database_name, collection_name, query } = req.body;
        if (!mongo_uri || !database_name || !collection_name || !query) {
            return res.status(400).json({
                error: "mongo_uri, database_name, collection_name, and query are required",
            });
        }
        const response = await axios.post(`${NLP_SERVICE_URL}/diagnose`, {
            mongo_uri, database_name, collection_name, query,
        });
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
        });
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
};
