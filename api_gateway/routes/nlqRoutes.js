const express = require("express");
const {
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
} = require("../controllers/nlqController");

const router = express.Router();

router.post("/connect-cluster", handleConnectCluster);
router.post("/get-collections", handleGetCollections);
router.post("/run-nlp", handleRunNLP);
router.post("/run-nlp-stream", handleRunNLPStream);
router.post("/get-schema", handleGetSchema);
router.post("/get-indexes", handleGetIndexes);
router.post("/diagnose", handleDiagnose);
router.post("/diagnose-schema", handleDiagnoseSchema);
router.post("/clear-cache", handleClearCache);
router.get("/llm-status", handleLLMStatus);

module.exports = router;
