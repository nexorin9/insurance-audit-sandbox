# Insurance Fly-Check Rules Drill Sandbox

Enables IT department / Medical Insurance Office to simulate fly-check inspection processes on desensitized data, proactively identifying high-risk fee items in the hospital. The system outputs a list of high-risk fee items and a rectification suggestion report (PDF/Word).

## Target Roles

- **IT Department**: Drill operator
- **Medical Insurance Office**: Report consumer
- **IT Department Head**: Progress supervisor

## Trigger Scenarios

Before monthly routine compliance checks, or after receiving early warnings from the medical insurance bureau: select a rule set, import desensitized fee data, run the drill, and output a rectification suggestion report.

## Minimum Data Contract

- **Input**: Fee details JSON + Rule set YAML
- **Output**: Drill results JSON + PDF/Word rectification suggestion report

## Tech Stack

- Python rule engine (core)
- Node.js/TypeScript frontend SPA
- FastAPI
- SQLite
- Docker

## Core Modules

- Rule engine (engine)
- Drill frontend (frontend SPA)
- API service
- Report generation
- Sample data synthesizer
- Configuration management & deployment

## Directory Structure

```
insurance-audit-sandbox/
├── src/
│   ├── engine/          # Rule engine (parser/executor/scorer/condition_ops)
│   ├── api/             # FastAPI service (routes/models/db)
│   ├── frontend/        # React SPA (Vite + TypeScript)
│   ├── report/          # Report generation (PDF/Word)
│   └── data_gen/        # Sample data synthesizer
├── data/                # Sample fee data
│   ├── fee_sample_50.json   # 50 sample fee records
│   └── fee_sample_100.json  # 100 sample fee records
├── templates/           # Report templates
├── rules/               # Rule set YAML
│   ├── zhongyao_injection_limit.yaml   # Traditional Chinese medicine injection limit rules
│   ├── material_markup_limit.yaml      # Material markup rate limit rules
│   ├── decomposition_suspicion.yaml     # Suspicious hospitalization decomposition rules
│   └── rules_index.yaml                # Rule set index
├── config.yaml           # Drill parameter configuration
├── .env.example          # Environment variable template
├── requirements.txt      # Python dependencies
├── package.json          # Node dependencies
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Installation

### Prerequisites

- Docker >= 20.10
- Docker Compose >= 2.0
- Python >= 3.10 (optional for local development)
- Node.js >= 18 (optional for local development)

### Docker Deployment (Recommended)

```bash
# Clone the project
git clone <repository-url>
cd insurance-audit-sandbox

# Start services
docker-compose up
```

After services start:
- API service: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173

### Local Development

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install frontend dependencies
cd src/frontend
npm install

# 3. Start frontend dev server
npm run dev

# 4. In another terminal, start API service
cd ../..
uvicorn src.api.main:app --reload --port 8000
```

## Configuration

### config.yaml

Drill parameters are defined in `config.yaml`:

```yaml
database:
  path: "data/sandbox.db"        # SQLite database path

log_level: "INFO"                 # Log level: DEBUG/INFO/WARNING

sandbox:
  default_rule_set: "zhongyao_injection_limit"
  risk_threshold_70: 70          # High risk threshold
  risk_threshold_90: 90          # Extremely high risk threshold
  report_format: "pdf"           # Default report format: pdf/docx
```

### Environment Variables (.env.example)

```bash
cp .env.example .env
# Edit .env with real values (optional)
```

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_PATH | SQLite database path | data/sandbox.db |
| LOG_LEVEL | Log level | INFO |
| API_PORT | API service port | 8000 |

## Usage

### Drill Execution Flow

**Step 1: Select Rule Set**

On the "Rule Set Management" page, view available rule sets (Traditional Chinese Medicine Injection Limit / Material Markup Rate Limit / Suspicious Hospitalization Decomposition), or upload a custom rule YAML.

**Step 2: Upload Fee Data**

On the "Drill Execution" page, upload a fee details JSON file (format see `data/fee_sample_50.json`), or use built-in synthetic data.

**Step 3: Execute Drill**

Click "Execute Drill" and the system will:
1. Load the selected rule set
2. Iterate through each fee detail and execute rule matching
3. Calculate risk scores and generate risk distribution statistics
4. Persist drill results to SQLite

**Step 4: View Results**

After the drill completes, view on the results page:
- High-risk fee item list (including item_id, category, amount, risk score)
- TOP high-risk category summary
- Risk distribution charts

**Step 5: Download Report**

Click "Generate Report", select PDF or Word format, and download the rectification suggestion report with corrective recommendations.

### API Call Examples

```bash
# Health check
curl http://localhost:8000/health

# List rule sets
curl http://localhost:8000/rules

# Execute drill
curl -X POST http://localhost:8000/sandbox/run \
  -H "Content-Type: application/json" \
  -d '{"rule_set_id": "zhongyao_injection_limit", "fee_items": [...] }'

# Generate report
curl -X POST http://localhost:8000/reports/generate?run_id=<run_id>&format=pdf \
  -o report.pdf
```

## Acceptance

### Demo Path

**Goal**: Complete end-to-end drill using synthetic data and verify PDF report content is complete.

**Steps**:

```bash
# 1. Start services
docker-compose up

# 2. Wait for services to be ready
curl http://localhost:8000/health
# Expected response: {"status": "ok", "timestamp": "..."}

# 3. Execute drill (using built-in 50 sample records)
curl -X POST http://localhost:8000/sandbox/run \
  -H "Content-Type: application/json" \
  -d '{
    "rule_set_id": "zhongyao_injection_limit",
    "fee_items": <content from data/fee_sample_50.json>
  }'
# Record the returned run_id

# 4. Generate PDF report
curl -X POST "http://localhost:8000/reports/generate?run_id=<run_id>&format=pdf" \
  -o report.pdf

# 5. Verify PDF content
# - Report cover includes drill name, rule set version, execution timestamp
# - High-risk item table includes item_id, category, amount, risk_score
# - TOP high-risk category summary
# - Rectification suggestions section

# 6. Stop services
docker-compose down
```

### Acceptance Checklist

- [ ] `docker-compose up` starts successfully without errors
- [ ] `GET /health` returns `status: ok`
- [ ] `GET /rules` returns at least 3 built-in rule sets
- [ ] After drill execution `hit_count > 0` (synthetic data contains boundary cases)
- [ ] PDF report downloadable with high-risk item list
- [ ] Dashboard list shows drill history records

## Security Extension

Current API authentication is **stub mode** (for development/demo). Before production deployment, replace with real authentication as follows.

### Current Implementation

- Checks `Authorization: Bearer <token>` or `X-API-Key` header
- If `API_AUTH_KEY` environment variable is not configured, **defaults to allow** (development mode) and logs a warning
- `/health`, `/ready`, `/docs`, `/openapi.json`, `/redoc` endpoints are exempt from authentication

### Enable Authentication

```bash
# Set API key (production mode)
export API_AUTH_KEY="your-secret-key-here"
export API_AUTH_DISABLED=""  # Ensure non-empty to enable authentication

# Or configure in .env
echo 'API_AUTH_KEY=your-secret-key-here' >> .env
echo 'API_AUTH_DISABLED=' >> .env
```

### Upgrade to Real JWT Verification

1. Install PyJWT:

```bash
pip install PyJWT
```

2. Modify the `_verify_token` function in `src/api/middleware/auth.py`:

```python
import jwt
from datetime import datetime, timezone

def _verify_token(token: str) -> bool:
    """Verify JWT token (replace this function with real JWT verification)"""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,          # Read from JWT_SECRET environment variable
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]}
        )
        # You can add business logic here: check user permissions, roles, etc.
        return True
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return False
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return False
```

3. Configure JWT secret before registering middleware in `src/api/main.py`:

```python
import os
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
```

### Production Deployment Checklist

- [ ] `API_AUTH_KEY` or `JWT_SECRET` is configured (default values are prohibited)
- [ ] `API_AUTH_DISABLED` is not set (ensure authentication is enabled)
- [ ] `/health` and `/ready` endpoints are exempt (health checks work without token)
- [ ] All business endpoints (`/rules`, `/sandbox/*`, `/reports/*`) require a valid token

## License

MIT License

---

## Support the Author

If you find this project helpful, feel free to buy me a coffee! ☕

![Buy Me a Coffee](buymeacoffee.png)

**Buy me a coffee (crypto)**

| Chain | Address |
|-------|---------|
| BTC | `bc1qc0f5tv577z7yt59tw8sqaq3tey98xehy32frzd` |
| ETH / USDT | `0x3b7b6c47491e4778157f0756102f134d05070704` |
| SOL | `6Xuk373zc6x6XWcAAuqvbWW92zabJdCmN3CSwpsVM6sd` |
