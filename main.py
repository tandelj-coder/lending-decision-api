"""
Lending Decision Assistant API
Author: Jigar Tandel | github.com/tandelj-coder

A FastAPI REST service that accepts a loan application payload,
queries the OpenAI API to generate a plain-English risk assessment,
and logs every decision to a local SQLite database.

Stack: FastAPI · Pydantic · OpenAI API · SQLite · pytest · Docker
"""

import os
import sqlite3
import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from openai import OpenAI

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Lending Decision Assistant API",
    description="LLM-powered risk assessment for retail loan applications.",
    version="1.0.0",
)

DB_PATH = os.getenv("DB_PATH", "assessments.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# ── Database init ─────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_id  TEXT,
            credit_score  INTEGER,
            annual_income REAL,
            loan_amount   REAL,
            employment    TEXT,
            decision      TEXT,
            summary       TEXT,
            created_at    TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ── Request / response models ─────────────────────────────────────────────────
class LoanApplication(BaseModel):
    applicant_id:  str   = Field(..., example="APP-1001")
    credit_score:  int   = Field(..., ge=300, le=850, example=720)
    annual_income: float = Field(..., gt=0,   example=65000.00)
    loan_amount:   float = Field(..., gt=0,   example=25000.00)
    employment:    str   = Field(..., example="Full-time")   # Full-time | Part-time | Self-employed | Unemployed


class AssessmentResponse(BaseModel):
    applicant_id: str
    decision:     str   # APPROVE | REVIEW | DECLINE
    summary:      str
    logged_at:    str


# ── Risk logic (rule-based pre-filter before LLM) ─────────────────────────────
def preliminary_decision(app: LoanApplication) -> str:
    dti = app.loan_amount / app.annual_income  # debt-to-income proxy

    if app.credit_score >= 700 and dti <= 0.4 and app.employment == "Full-time":
        return "APPROVE"
    if app.credit_score < 550 or app.employment == "Unemployed":
        return "DECLINE"
    return "REVIEW"


# ── LLM risk summary ──────────────────────────────────────────────────────────
def generate_summary(app: LoanApplication, decision: str) -> str:
    if not OPENAI_API_KEY:
        # Fallback when no API key is set (local dev / CI)
        return (
            f"[Offline mode] Applicant {app.applicant_id}: credit score {app.credit_score}, "
            f"income ${app.annual_income:,.0f}, loan request ${app.loan_amount:,.0f}, "
            f"employment '{app.employment}'. Preliminary decision: {decision}."
        )

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        f"You are a retail lending risk analyst. Summarize this loan application in 2-3 sentences "
        f"and explain the key factors behind the '{decision}' decision.\n\n"
        f"Applicant ID: {app.applicant_id}\n"
        f"Credit Score: {app.credit_score}\n"
        f"Annual Income: ${app.annual_income:,.0f}\n"
        f"Loan Amount Requested: ${app.loan_amount:,.0f}\n"
        f"Loan-to-Income Ratio: {app.loan_amount / app.annual_income:.2f}\n"
        f"Employment Status: {app.employment}\n"
        f"Decision: {decision}"
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/assess", response_model=AssessmentResponse)
def assess(application: LoanApplication):
    decision = preliminary_decision(application)

    try:
        summary = generate_summary(application, decision)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")

    now = datetime.datetime.utcnow().isoformat()

    # Log to SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO assessments
           (applicant_id, credit_score, annual_income, loan_amount, employment, decision, summary, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (application.applicant_id, application.credit_score, application.annual_income,
         application.loan_amount, application.employment, decision, summary, now),
    )
    conn.commit()
    conn.close()

    return AssessmentResponse(
        applicant_id=application.applicant_id,
        decision=decision,
        summary=summary,
        logged_at=now,
    )


@app.get("/assessments")
def list_assessments(limit: int = 20):
    """Return the most recent assessments from the log."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, applicant_id, credit_score, loan_amount, decision, created_at "
        "FROM assessments ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [
        {
            "id": r[0], "applicant_id": r[1], "credit_score": r[2],
            "loan_amount": r[3], "decision": r[4], "created_at": r[5],
        }
        for r in rows
    ]
