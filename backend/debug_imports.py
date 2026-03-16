"""Run this to see which import hangs:  python debug_imports.py"""
import sys

def step(name):
    sys.stderr.write(f"  ... {name}\n")
    sys.stderr.flush()

step("config")
from config import AWS_REGION, BEDROCK_MODEL_ID
step("models")
from models import ClassifyResponse, FeedbackRequest, FeedbackResponse
step("database")
from database import generate_interaction_id, init_db, log_event, record_feedback, get_stats
step("agent")
from agent import apply_agent
step("ai_client (boto3)")
from ai_client import classify_image
step("fastapi")
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
step("done")
sys.stderr.write("All imports OK.\n")
sys.stderr.flush()
