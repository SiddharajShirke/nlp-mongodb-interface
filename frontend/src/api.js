import axios from "axios";

const API_BASE = "http://localhost:5000/api/nlq";

// Step 1 — Connect to cluster and list databases
export const connectCluster = async (mongoUri) => {
    const response = await axios.post(`${API_BASE}/connect-cluster`, {
        mongo_uri: mongoUri,
    });
    return response.data;
};

// Step 2 — List collections in a database (with doc counts)
export const getCollections = async (mongoUri, databaseName) => {
    const response = await axios.post(`${API_BASE}/get-collections`, {
        mongo_uri: mongoUri,
        database_name: databaseName,
    });
    return response.data;
};

// Step 3 — Run NLP query on a specific collection (with pagination)
export const runNLP = async (mongoUri, databaseName, collectionName, query, page = 1, pageSize = 20) => {
    const response = await axios.post(`${API_BASE}/run-nlp`, {
        mongo_uri: mongoUri,
        database_name: databaseName,
        collection_name: collectionName,
        query,
        page,
        page_size: pageSize,
    });
    return response.data;
};

// Get schema for a collection
export const getSchema = async (mongoUri, databaseName, collectionName) => {
    const response = await axios.post(`${API_BASE}/get-schema`, {
        mongo_uri: mongoUri,
        database_name: databaseName,
        collection_name: collectionName,
    });
    return response.data;
};

// Get indexes for a collection
export const getIndexes = async (mongoUri, databaseName, collectionName) => {
    const response = await axios.post(`${API_BASE}/get-indexes`, {
        mongo_uri: mongoUri,
        database_name: databaseName,
        collection_name: collectionName,
    });
    return response.data;
};

// Diagnose — full pipeline trace for a query
export const diagnoseQuery = async (mongoUri, databaseName, collectionName, query) => {
    const response = await axios.post(`${API_BASE}/diagnose`, {
        mongo_uri: mongoUri,
        database_name: databaseName,
        collection_name: collectionName,
        query,
    });
    return response.data;
};

// Diagnose schema — inspect flattened schema fields
export const diagnoseSchema = async (mongoUri, databaseName, collectionName) => {
    const response = await axios.post(`${API_BASE}/diagnose-schema`, {
        mongo_uri: mongoUri,
        database_name: databaseName,
        collection_name: collectionName,
    });
    return response.data;
};

// Clear server-side schema cache
export const clearCache = async () => {
    const response = await axios.post(`${API_BASE}/clear-cache`);
    return response.data;
};
