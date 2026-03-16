"""
Run the EcoNova Guardian API. Quiet logs; no reload by default (no venv watch spam).
Usage: from backend/ run:  python run.py
"""
import sys

def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()

if __name__ == "__main__":
    log("1. Importing uvicorn...")
    import uvicorn
    log("2. Importing config...")
    from config import AWS_REGION, BEDROCK_MODEL_ID
    log("3. Importing models...")
    from models import ClassifyResponse, FeedbackRequest, FeedbackResponse
    log("4. Importing database...")
    from database import generate_interaction_id, init_db, log_event, record_feedback, get_stats
    log("5. Importing agent...")
    from agent import apply_agent
    log("6. Importing FastAPI...")
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    log("7. Building app...")
    from main import app
    log("Starting server at http://127.0.0.1:8000 ...")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
