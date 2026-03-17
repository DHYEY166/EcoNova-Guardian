"""
Agent logic: confidence thresholds and decision mode (DIRECT / UNCERTAIN / NEEDS_CLARIFICATION).
"""
from __future__ import annotations

from config import CONF_HIGH, CONF_MED

# Predefined clarification options for low-confidence cases (avoids extra Nova call)
CLARIFICATION_TEMPLATES = {
    "default": {
        "question": "This item could go in more than one bin. Which best describes it?",
        "options": ["Mostly clean recyclable (e.g. rinsed container)", "Dirty or food-soiled", "Compostable (food/organic)"],
    },
    "packaging": {
        "question": "Is this packaging clean or contaminated?",
        "options": ["Clean – can be recycled", "Dirty or greasy – trash", "Compostable packaging"],
    },
    "paper_cardboard": {
        "question": "Is the paper/cardboard clean or greasy?",
        "options": ["Clean – recycling", "Greasy or food-soiled – trash or compost", "Mixed – tear off clean part for recycling"],
    },
}


def get_decision_mode(confidence: float) -> str:
    if confidence >= CONF_HIGH:
        return "DIRECT"
    if confidence >= CONF_MED:
        return "UNCERTAIN"
    return "NEEDS_CLARIFICATION"


def get_clarification(nova_output: dict) -> tuple[str | None, list[str] | None]:
    """Return (clarification_question, clarification_options) for low-confidence. Otherwise (None, None)."""
    mode = get_decision_mode(nova_output.get("confidence", 0))
    if mode != "NEEDS_CLARIFICATION":
        return None, None
    material = (nova_output.get("material") or "").lower()
    if "paper" in material or "cardboard" in material:
        t = CLARIFICATION_TEMPLATES["paper_cardboard"]
        return t["question"], t["options"]
    if "plastic" in material or "packaging" in material:
        t = CLARIFICATION_TEMPLATES["packaging"]
        return t["question"], t["options"]
    t = CLARIFICATION_TEMPLATES["default"]
    return t["question"], t["options"]


def apply_agent(nova_output: dict) -> dict:
    """Add decision_mode, clarification_question, clarification_options to Nova output."""
    out = dict(nova_output)
    out["decision_mode"] = get_decision_mode(out.get("confidence", 0))
    q, opts = get_clarification(out)
    out["clarification_question"] = q
    out["clarification_options"] = opts
    return out
