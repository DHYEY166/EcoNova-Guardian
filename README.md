# EcoNova Guardian

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock%20%7C%20Nova%20Lite-orange)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-teal)

Real-time waste classification powered by Amazon Nova on AWS Bedrock.
Point a camera at an item and get a bin recommendation:
- **WASTE**
- **RECYCLING**
- **COMPOST**

The app includes smart frame gating to reduce unnecessary Bedrock calls, feedback capture, and simple analytics.

---

## Demo

[![EcoNova Guardian Demo](https://img.youtube.com/vi/oic2QKJ9irc/maxresdefault.jpg)](https://youtu.be/oic2QKJ9irc)

![EcoNova Guardian](EcoNova%20Guardia.png)

---

## Deployment

Deploy to your own EC2 instance following the steps in [AWS Deployment](#aws-deployment-initial-setup) below.
Once running, your app will be available at `https://<your-ec2-ip>.sslip.io` (with certbot TLS).

Current hosting stack:
- EC2 (Amazon Linux 2023)
- FastAPI backend as a systemd service (`econova`)
- nginx serving frontend and proxying API
- Let's Encrypt certificate via certbot
- Bedrock auth through EC2 IAM role (no hardcoded AWS keys)

---

## Features

- Live camera-based classification
- Smart change detection to avoid wasteful inference calls
- Auto-clear when object leaves frame
- Confidence-based agent decision modes
- Feedback endpoint for corrections
- SQLite analytics dashboard data

---

## Project Structure

```text
EcoNova-Guardian/
├── README.md
├── activate_envs.sh
├── backend/
│   ├── main.py
│   ├── ai_client.py
│   ├── agent.py
│   ├── models.py
│   ├── database.py
│   ├── config.py
│   ├── prompts.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── deploy/
│   ├── bedrock-policy.json
│   ├── econova.service
│   ├── nginx.conf
│   ├── bootstrap.sh
│   └── deploy_update.sh
└── data/
    └── test_images/     # gitkeep only; drop test images here locally
```

---

## Local Development

### Prerequisites

- Python 3.10+
- AWS Bedrock access in your AWS account
- Browser with camera permission

### Quick start

> **macOS only.** `activate_envs.sh` activates the backend venv, auto-installs
> dependencies when `requirements.txt` changes, opens the frontend server in a
> new Terminal window, and starts the FastAPI backend — all in one step.

```bash
cd EcoNova-Guardian
source activate_envs.sh
```

Flags:
- `--force-install` — re-run `pip install` even if requirements haven't changed
- `--dev-reload` — start uvicorn with `--reload` for live code reloading

Then open:
- http://localhost:8080

### Manual start (optional)

Backend:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
python3 -m http.server 8080
```

---

## Environment Variables

Use `.env` for local dev values.

Required for local runs:

```bash
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0
```

Optional local keys (if not using profile/role):

```bash
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
```

Other optional settings:

```bash
CONF_HIGH=0.85
CONF_MED=0.7
BEDROCK_DAILY_CAP=0
DATABASE_PATH=data/events.db
```

### EC2 note

On EC2, prefer IAM role auth.
Do not keep static access keys in `.env` on server.

---

## API Endpoints

- `GET /health`
- `POST /classify` (multipart form-data with image)
- `POST /feedback`
- `GET /stats`

---

## AWS Deployment (Initial Setup)

1. Create IAM policy from `deploy/bedrock-policy.json`
2. Create IAM role for EC2 and attach that policy
3. Launch EC2 instance (open 22, 80, 443)
4. Attach the IAM role to the instance
5. Run server bootstrap steps (install python/nginx, configure services, certbot)

This repo includes:
- `deploy/econova.service`
- `deploy/nginx.conf`
- `deploy/bootstrap.sh`

---

## Deploy Updates (One Command)

After initial EC2 setup, deploy code changes from your local machine with:

```bash
./deploy/deploy_update.sh
```

What it does:
- Syncs `backend/`, `frontend/`, and `deploy/` to EC2
- Installs Python dependencies
- Restarts `econova`
- Reloads `nginx`
- Prints health check output

Optional overrides:

```bash
EC2_HOST=<your-ec2-ip> EC2_KEY=~/Downloads/econova-key.pem ./deploy/deploy_update.sh
```

---

## Troubleshooting

### 500 from nginx on `/`

Likely file permission issue on frontend files.
Ensure nginx can read:
- `/home/ec2-user`
- `/home/ec2-user/app`
- `/home/ec2-user/app/frontend/*`

### 502 on `/classify`

Backend upstream failed. Check:

```bash
sudo systemctl status econova --no-pager
sudo journalctl -u econova -n 120 --no-pager
```

### Bedrock AccessDenied with region in error

Update IAM policy to allow `bedrock:InvokeModel` for Nova Lite model/inference profile resources used at runtime.

### ExpiredTokenException

Remove temporary static keys from server `.env` and use EC2 IAM role credentials.

---

## Cost Notes (Approx)

- EC2 `t3.micro`: about $7-8/month outside free tier
- Bedrock Nova Lite: low cost for hackathon demo traffic

Always stop/terminate EC2 when not demoing.

---

## Built With

- Python, FastAPI, Uvicorn
- Vanilla JavaScript, HTML, CSS
- SQLite
- AWS Bedrock + Amazon Nova Lite
- nginx + systemd + certbot

---

Built for the Amazon Nova AI Hackathon.
