# EcoNova Guardian: Agentic Waste Sorting Assistant

**Real-time waste classification powered by Amazon Nova on AWS Bedrock.** Point your camera at a waste item and get instant bin recommendations (Waste / Recycling / Compost) with reasoning and sorting tips.

## Features

- **Live Camera Feed**: Real-time classification with no preprocessing—full-frame capture for complete context
- **Smart Bedrock Gating**: Signature-based change detection prevents wasteful API calls; achieves ~95% cost reduction
- **Auto-Clear Results**: Result cards automatically disappear when items are removed from the camera view
- **Robust Noise Handling**: Multi-tick confirmation thresholds prevent false positives on blank scenes with camera noise
- **User Feedback Loop**: Track accuracy and collect corrections for future model retraining
- **Analytics Dashboard**: View total items classified, overall accuracy, and per-category performance
- **Zero Build Setup**: Single command to start both backend and frontend servers

---

## Quick Start

### Prerequisites

- macOS/Linux with Python 3.12+
- AWS credentials in `.env` (already set up)
- Modern browser with camera access (Chrome, Safari, Firefox)

### 1. One-Command Startup

```bash
cd "/Users/dhyeydesai/Desktop/Amazon Nova AI Hackathon"
source activate_envs.sh
```

This script:
- Activates the Python virtual environment
- Skips pip install if `requirements.txt` hasn't changed (SHA-256 fingerprinting)
- Starts the FastAPI backend on port 8000
- Starts the frontend on port 8080 (opens in new Terminal tab)

Then open your browser to **http://localhost:8080**.

### 2. Manual Setup (if needed)

**Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level warning
```

**Frontend:**
```bash
cd frontend
python3 -m http.server 8080
```

Open **http://localhost:8080** in your browser.

---

## Usage

1. **Start Camera**: Click "Use camera" and allow camera access
2. **Point & Wait**: Aim at a waste item—after ~2.1s of sustained change, Bedrock fires
3. **See Results**: Item is classified, bin opens, reasoning + tips displayed
4. **Give Feedback**: Click "Was this correct?" to improve accuracy; corrections are logged
5. **View Stats**: Click "Stats" for accuracy metrics and classification history

**Tip**: For best results, hold the item clearly in frame and avoid rapid motion.

---

## How It Works

### Smart Frame Gating (Cost Optimization)

Instead of calling Bedrock on every 700ms camera tick:

1. **Signature Generation**: Each frame is downsampled to a 24×24 grayscale signature (~576 bytes)
2. **Change Detection**: Compare pixel differences between consecutive frames
3. **Multi-Tick Confirmation**:
   - Frame diff ≥ 10 → increment change counter
   - Change counter reaches 3 → send to Bedrock (2.1s threshold)
4. **Return to Baseline**:
   - Frame matches baseline within 6 units → increment reset counter
   - Reset counter reaches 2 → clear result card, hide bins (1.4s total)

Result: ~95% fewer Bedrock API calls compared to naive per-tick classification.

### Full-Frame Capture

The camera feed is sent **in full** to Amazon Nova, not cropped. This provides the model with complete spatial context for better classification confidence.

### Bedrock Integration

- **Model**: `us.amazon.nova-lite-v1:0` (fast, cost-effective)
- **Prompt**: Explicit hints to ignore body parts, backgrounds, non-waste clutter
- **Fallback**: If model returns `category: "none"`, result is silently discarded
- **Rate Limiting**: Minimum 3.5s between Bedrock calls

---

## Architecture

```
┌─────────────┐
│   Browser   │
│  (Camera)   │
└──────┬──────┘
       │ POST /classify (full frame)
       │
┌──────▼──────────────────┐
│   FastAPI Backend       │
│  (http://localhost:8000)│
├─────────────────────────┤
│ - Image validation      │
│ - Bedrock API calls     │
│ - Analytics logging     │
│ - Feedback storage      │
└──────┬──────────────────┘
       │ boto3 SDK
       │
┌──────▼──────────────────┐
│  AWS Bedrock            │
│  (us-east-1)            │
├─────────────────────────┤
│ Amazon Nova Lite Model  │
└─────────────────────────┘
```

---

## Configuration & Tuning

### Frame Gating Thresholds

Edit `frontend/app.js` to adjust (all times in milliseconds):

```javascript
const SCENE_CHANGE_THRESHOLD = 10         // Min pixel diff to count as change
const CHANGE_TICKS_REQUIRED = 3           // Ticks to sustain before Bedrock call (3 × 700ms = 2.1s)
const SCENE_RESET_THRESHOLD = 6           // Pixel diff to count as "back to baseline"
const RESET_STABLE_TICKS_REQUIRED = 2     // Ticks to sustain before clearing result (2 × 700ms = 1.4s)
const OBJECT_SWAP_THRESHOLD = 10          // Pixel diff from last classified to trigger new Bedrock call
const AUTO_CLASSIFY_INTERVAL_MS = 700     // Frequency of frame checks
const MIN_CLASSIFY_GAP_MS = 3500          // Minimum time between Bedrock requests
```

### AWS Configuration

In `.env`:

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

Optional cost cap:
```
BEDROCK_DAILY_CAP=100  # Requests/day
```

---

## API Reference

| Endpoint   | Method | Body | Response |
|-----------|--------|------|----------|
| `/health` | GET | — | `{"status": "ok"}` |
| `/classify` | POST | `FormData{image, description}` | `{category, item_name, confidence, reasoning, tips, decision_mode, clarification_question, clarification_options, interaction_id}` |
| `/feedback` | POST | `{interaction_id, final_category, was_correct}` | `{success: true}` |
| `/stats` | GET | — | `{total_items, accuracy_overall, items_diverted_from_landfill, accuracy_per_category, ...}` |

---

## Project Structure

```
Amazon Nova AI Hackathon/
├── README.md                    (this file)
├── ABOUT.md                     (project story & learnings)
├── smart-sorting-plan.md        (initial project plan)
├── activate_envs.sh             (startup script with smart pip caching)
├── .env                         (AWS credentials; keep secret)
├── backend/
│   ├── main.py                  (FastAPI app & endpoints)
│   ├── ai_client.py             (Bedrock integration)
│   ├── agent.py                 (classification logic)
│   ├── models.py                (Pydantic schemas)
│   ├── database.py              (SQLite operations)
│   ├── config.py                (settings & env loading)
│   ├── prompts.py               (Bedrock prompt templates)
│   ├── requirements.txt          (Python dependencies)
│   ├── .requirements.sha256      (fingerprint for smart caching)
│   ├── venv/                    (Python virtual environment)
│   └── __pycache__/             (compiled Python cache)
├── frontend/
│   ├── index.html               (camera UI, bins, result card)
│   ├── app.js                   (camera capture, frame gating, Bedrock calls)
│   ├── styles.css               (responsive layout, animations)
│   └── favicon.ico              (empty favicon to prevent 404)
└── data/
    ├── test_images/             (optional test waste images)
    ├── econova.db               (SQLite feedback & analytics)
    └── .bedrock_requests.txt    (request count tracking)
```

---

## Environment Variables

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AWS_SESSION_TOKEN=<optional-for-temp-credentials>
AWS_REGION=us-east-1

# Bedrock Configuration
BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0

# Optional Cost Controls
BEDROCK_DAILY_CAP=100  # Max requests per day
```

---

## Performance & Cost

- **Bedrock Calls**: Reduced to ~5-10 per minute of active use (vs. 85+ per minute without gating)
- **Latency**: Classification result in 1-2 seconds after sustained item detection
- **Cost/1M Invocations**: ~$0.30 (Bedrock pricing for Nova Lite vision)
- **Estimated Monthly Cost**: <$5 with 1000 daily users @ 10 classifications each

---

## Troubleshooting

**405/415 errors on `/classify`**: Ensure `Content-Type: multipart/form-data` with image binary included.

**Camera permission denied**: Check browser settings → Camera → Allow for localhost.

**"metal can" classification when empty**: Signature thresholds are tuned to prevent this. If it persists:
- Increase `CHANGE_TICKS_REQUIRED` to 4
- Increase `SCENE_CHANGE_THRESHOLD` to 12

**Slow startup**: First run does pip install. After that, `activate_envs.sh` uses SHA-256 fingerprinting to skip reinstall if requirements.txt is unchanged.

**Bedrock timeouts**: Check AWS credentials and region (`us-east-1`). Ensure IAM user has `bedrock:InvokeModel` permission.

---

## Startup Script Flags

Use `activate_envs.sh` with optional flags:

```bash
# Standard: no pip install (if unchanged), no hot-reload
source activate_envs.sh

# Force reinstall dependencies
source activate_envs.sh --force-install

# Enable hot-reload (uvicorn --reload with watched directories)
source activate_envs.sh --dev-reload

# Both
source activate_envs.sh --force-install --dev-reload
```

---

## Built With

Python 3.12, FastAPI, Uvicorn, JavaScript ES6+, HTML5, CSS3, Bash, pydantic, python-dotenv, loguru, Pillow, Vanilla JavaScript, HTML5 Canvas API, MediaDevices API, Fetch API, CSS3 animations, Amazon Bedrock, Amazon Nova (us.amazon.nova-lite-v1:0), boto3, SQLite, AWS, osascript, SHA-256 fingerprinting

---

## Future Enhancements

- Mobile app (iOS/Android) with AR bin overlays
- Multi-language support (Spanish, Mandarin, etc.)
- Community leaderboards & gamification
- IoT smart bin integration for tracking
- Sustainability metrics (CO₂ saved, landfill diversion)
- Edge deployment (model distillation)

---

## License & Attribution

Built for the **Amazon Nova AI Hackathon**. Uses AWS Bedrock and Amazon Nova foundation models.

---

**Smart sorting. Less waste. Better planet.**
