"""Configuration from environment variables. Never commit .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# AWS (supports temporary credentials with AWS_SESSION_TOKEN)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN", "")  # optional, for temporary creds
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
# Use inference profile for Nova (required for on-demand Converse). Base model ID not supported.
_default_nova = "us.amazon.nova-lite-v1:0"
_raw = os.getenv("BEDROCK_MODEL_ID", _default_nova)
# If user set base model ID, use US inference profile instead
BEDROCK_MODEL_ID = _raw if _raw.startswith(("us.", "apac.", "eu.")) or "/" in _raw else _default_nova

# Agent confidence thresholds
CONF_HIGH = float(os.getenv("CONF_HIGH", "0.85"))
CONF_MED = float(os.getenv("CONF_MED", "0.7"))

# Cost guardrail: log and optionally cap Bedrock requests per day (0 = no cap)
BEDROCK_DAILY_CAP = int(os.getenv("BEDROCK_DAILY_CAP", "0"))

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "events.db"))
