"""
EcoNova Guardian – Agentic Waste Sorting Assistant
FastAPI backend: /health, /classify, /feedback, /stats
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from agent import apply_agent
from config import AWS_REGION, BEDROCK_MODEL_ID
from database import (
    generate_interaction_id,
    init_db,
    log_event,
    record_feedback,
    get_stats,
)
from models import ClassifyResponse, FeedbackRequest, FeedbackResponse

app = FastAPI(
    title="EcoNova Guardian API",
    description="Agentic waste sorting assistant powered by Amazon Nova",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    sys.stderr.write("Server ready → http://127.0.0.1:8000/docs\n")
    sys.stderr.flush()


@app.get("/health")
def health():
    """Health check for deployment and load balancers."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "region": AWS_REGION,
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/classify", response_model=ClassifyResponse)
async def classify(
    image: UploadFile = File(...),
    description: str | None = Form(None),
):
    """Classify a waste item from image (and optional description) using Amazon Nova."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (e.g. image/jpeg, image/png)")
    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")
    from ai_client import classify_image
    try:
        nova_out = classify_image(image_bytes, description)
    except Exception as e:
        logger.exception("Bedrock classify failed")
        raise HTTPException(status_code=502, detail=f"Classification failed: {str(e)}")
    out = apply_agent(nova_out)
    interaction_id = generate_interaction_id()
    had_clarification = out.get("decision_mode") == "NEEDS_CLARIFICATION"
    log_event(
        interaction_id=interaction_id,
        item_name=out.get("item_name", "Unknown"),
        predicted_category=out["category"],
        final_category=out["category"],
        confidence=out.get("confidence", 0),
        decision_mode=out.get("decision_mode", "DIRECT"),
        had_clarification=had_clarification,
        was_correct=None,
    )
    return ClassifyResponse(
        interaction_id=interaction_id,
        category=out["category"],
        item_name=out.get("item_name", "Unknown"),
        material=out.get("material", ""),
        confidence=out["confidence"],
        reasoning=out.get("reasoning", ""),
        tips=out.get("tips", ""),
        decision_mode=out["decision_mode"],
        clarification_question=out.get("clarification_question"),
        clarification_options=out.get("clarification_options"),
    )


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(body: FeedbackRequest):
    """Record user feedback (correct/incorrect and final category)."""
    try:
        record_feedback(body.interaction_id, body.final_category, body.was_correct)
        return FeedbackResponse(status="success", message="Feedback recorded")
    except Exception as e:
        return FeedbackResponse(status="error", message=str(e))


@app.get("/stats")
def stats():
    """Aggregated analytics: accuracy, confusion matrix, top confusing items."""
    return get_stats()


# So you can see when the app has loaded (before server binds)
sys.stderr.write("App loaded, starting server...\n")
sys.stderr.flush()
