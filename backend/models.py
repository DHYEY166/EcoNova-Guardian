"""Pydantic request/response schemas for EcoNova Guardian API."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# --- Classify ---
class ClassifyResponse(BaseModel):
    """Response from POST /classify."""
    interaction_id: str
    category: Literal["WASTE", "RECYCLING", "COMPOST"]
    item_name: str
    material: str = ""
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    tips: str
    decision_mode: Literal["DIRECT", "UNCERTAIN", "NEEDS_CLARIFICATION"]
    clarification_question: str | None = None
    clarification_options: list[str] | None = None


# --- Feedback ---
class FeedbackRequest(BaseModel):
    """Request body for POST /feedback."""
    interaction_id: str
    final_category: Literal["WASTE", "RECYCLING", "COMPOST"]
    was_correct: bool


class FeedbackResponse(BaseModel):
    """Response from POST /feedback."""
    status: Literal["success", "error"]
    message: str


# --- Traffic (anonymous) ---
class VisitRequest(BaseModel):
    """POST /visit — browser-generated UUID, one successful ping per UTC day."""
    visitor_id: UUID


# --- Stats ---
class StatsResponse(BaseModel):
    """Response from GET /stats."""
    total_items: int
    accuracy_overall: float
    accuracy_per_category: dict[str, float]
    confusion_matrix: list[list[int]]
    top_confusing_items: list[dict]
    items_diverted_from_landfill: int
    visitors_today: int = 0
    visitors_last_7_days: int = 0
    visitors_all_time: int = 0
