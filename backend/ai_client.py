"""
Amazon Bedrock / Nova client for image classification.
Uses Converse API with image + system prompt. Logs request count for $100 credit awareness.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import boto3
from loguru import logger

from config import (
    AWS_REGION,
    BEDROCK_DAILY_CAP,
    BEDROCK_MODEL_ID,
)
from prompts import SYSTEM_PROMPT, user_prompt

_count_file = Path(__file__).resolve().parent.parent / "data" / ".bedrock_requests.txt"


def _get_and_increment_count() -> int:
    """Return today's request count after incrementing. Resets automatically each calendar day."""
    today = str(date.today())
    count = 0
    try:
        if _count_file.exists():
            parts = _count_file.read_text().strip().split(",")
            if len(parts) == 2 and parts[0] == today:
                count = int(parts[1])
    except Exception:
        pass
    count += 1
    try:
        _count_file.parent.mkdir(parents=True, exist_ok=True)
        _count_file.write_text(f"{today},{count}")
    except Exception:
        pass
    return count


def _create_client():
    return boto3.client("bedrock-runtime", region_name=AWS_REGION)


def _infer_image_format(image_bytes: bytes) -> str:
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if image_bytes[:2] in (b"\xff\xd8", b"\xFF\xD8"):
        return "jpeg"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    return "jpeg"


def classify_image(image_bytes: bytes, description: str | None = None) -> dict:
    """
    Call Amazon Nova via Bedrock Converse API with image + optional text.
    Returns dict with category, item_name, material, confidence, reasoning, tips.
    """
    count = _get_and_increment_count()
    if BEDROCK_DAILY_CAP and count > BEDROCK_DAILY_CAP:
        raise RuntimeError("Daily Bedrock request cap reached. Check BEDROCK_DAILY_CAP.")
    logger.info("Bedrock request #{} (model={})", count, BEDROCK_MODEL_ID)

    client = _create_client()
    img_fmt = _infer_image_format(image_bytes)
    user_text = user_prompt(description)

    messages = [
        {
            "role": "user",
            "content": [
                {"image": {"format": img_fmt, "source": {"bytes": image_bytes}}},
                {"text": user_text},
            ],
        }
    ]
    system = [{"text": SYSTEM_PROMPT}]

    response = client.converse(
        modelId=BEDROCK_MODEL_ID,
        messages=messages,
        system=system,
        inferenceConfig={"maxTokens": 1024, "temperature": 0.2},
    )

    output = response.get("output", {})
    content_blocks = output.get("message", {}).get("content", [])
    text = ""
    for block in content_blocks:
        if "text" in block:
            text += block["text"]

    # Parse JSON from model output (allow markdown code block)
    text = text.strip()
    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        logger.warning("No JSON found in model output: {}", text[:500])
        return {
            "category": "WASTE",
            "item_name": "Unknown",
            "material": "Unknown",
            "confidence": 0.0,
            "reasoning": "Could not parse model response.",
            "tips": "When in doubt, check local guidelines.",
        }
    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error: {} in {}", e, json_match.group()[:200])
        return {
            "category": "WASTE",
            "item_name": "Unknown",
            "material": "Unknown",
            "confidence": 0.0,
            "reasoning": "Invalid model response format.",
            "tips": "When in doubt, check local guidelines.",
        }

    category = (data.get("category") or "WASTE").upper()
    if category not in ("WASTE", "RECYCLING", "COMPOST"):
        category = "WASTE"
    return {
        "category": category,
        "item_name": data.get("item_name", "Unknown"),
        "material": data.get("material", ""),
        "confidence": float(data.get("confidence", 0.5)),
        "reasoning": data.get("reasoning", ""),
        "tips": data.get("tips", ""),
    }
