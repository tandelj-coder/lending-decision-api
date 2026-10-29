# Lending Decision Assistant API

A FastAPI REST service that accepts retail loan application data, applies rule-based risk logic, generates a plain-English risk summary via OpenAI's GPT-3.5-turbo, and logs every decision to a local SQLite database.

**Stack:** FastAPI · Pydantic · OpenAI API · SQLite · pytest · Docker

---

## Features

- **POST /assess** — Submit a loan application and receive an APPROVE / REVIEW / DECLINE decision with an LLM-generated risk summary
- **GET /assessments** — List recent decisions from the SQLite log
- **GET /health** — Liveness check
- Rule-based pre-filter (credit score, debt-to-income ratio, employment status) runs before any LLM call
- Offline fallback: works without an OpenAI API key (returns a structured text summary instead)
- ETL-style logging: every assessment is persisted to SQLite for downstream reporting

---

## Quickstart

### Local (Python)

```bash
# 1. Clone and install
git clone https://github.com/tandelj-coder/lending-decision-api.git
cd lending-decision-api
pip install -r requirements.txt

# 2. (Optional) Set your OpenAI key — omit to run in offline mode
export OPENAI_API_KEY=sk-...

# 3. Start the server
uvicorn main:app --reload

# 4. Open the interactive docs
open http://localhost:8000/docs
```

### Docker

```bash
docker build -t lending-decision-api .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... lending-decision-api
```

---

## API Usage

### Assess a loan application

```bash
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{
    "applicant_id": "APP-1001",
    "credit_score": 720,
    "annual_income": 75000,
    "loan_amount": 25000,
    "employment": "Full-time"
  }'
```

**Response:**
```json
{
  "applicant_id": "APP-1001",
  "decision": "APPROVE",
  "summary": "Applicant APP-1001 presents a strong profile with a credit score of 720, an annual income of $75,000, and a manageable loan-to-income ratio of 0.33. Full-time employment further supports the APPROVE decision.",
  "logged_at": "2026-10-29T14:23:01.123456"
}
```

### Decision logic

| Condition | Decision |
|-----------|----------|
| Credit score >= 700 AND DTI <= 0.40 AND Full-time | APPROVE |
| Credit score < 550 OR Unemployed | DECLINE |
| All other cases | REVIEW |

DTI = `loan_amount / annual_income`

### Employment values accepted
`Full-time` · `Part-time` · `Self-employed` · `Unemployed`

### List recent assessments

```bash
curl http://localhost:8000/assessments?limit=10
```

---

## Running Tests

```bash
pytest test_main.py -v
```

7 tests cover: rule-based decision logic (approve / decline / review), API endpoint responses, Pydantic validation errors, and the assessments log endpoint.

---

## Project Structure

```
lending-decision-api/
├── main.py            # FastAPI app — routes, models, decision logic, SQLite logging
├── test_main.py       # pytest test suite (7 tests)
├── Dockerfile         # python:3.11-slim image, uvicorn on port 8000
├── requirements.txt   # pinned dependencies
├── .gitignore
└── README.md
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `""` | OpenAI key — omit to run in offline mode |
| `DB_PATH` | `assessments.db` | Path to the SQLite database file |

---

## Author

**Jigar Tandel** — [github.com/tandelj-coder](https://github.com/tandelj-coder)
