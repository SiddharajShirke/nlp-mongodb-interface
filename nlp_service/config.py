import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# ---- LLM / AI Integration ----
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Set to "llm" to use LLM as primary parser, "rule" for rule-based only,
# or "auto" (default) to try LLM first and fall back to rule-based.
PARSER_MODE = os.getenv("PARSER_MODE", "auto")
