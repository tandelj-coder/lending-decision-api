"""
Unit tests for Lending Decision Assistant API
Run: pytest test_main.py -v
"""

import pytest
from fastapi.testclient import TestClient
from main import app, preliminary_decision, LoanApplication

client = TestClient(app)


# ── preliminary_decision unit tests ───────────────────────────────────────────

def make_app(**kwargs):
    defaults = {
        "applicant_id": "TEST-001",
        "credit_score": 720,
        "annual_income": 70000,
        "loan_amount": 20000,
        "employment": "Full-time",
    }
    defaults.update(kwargs)
    return LoanApplication(**defaults)


def test_approve_strong_applicant():
    result = preliminary_decision(make_app(credit_score=750, annual_income=80000, loan_amount=20000))
    assert result == "APPROVE"


def test_decline_low_credit():
    result = preliminary_decision(make_app(credit_score=500))
    assert result == "DECLINE"


def test_decline_unemployed():
    result = preliminary_decision(make_app(employment="Unemployed"))
    assert result == "DECLINE"


def test_review_borderline():
    # Good credit but high loan-to-income ratio
    result = preliminary_decision(make_app(credit_score=680, annual_income=50000, loan_amount=30000))
    assert result == "REVIEW"


# ── API endpoint tests ─────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_assess_returns_decision():
    payload = {
        "applicant_id": "APP-TEST",
        "credit_score": 750,
        "annual_income": 90000,
        "loan_amount": 25000,
        "employment": "Full-time",
    }
    r = client.post("/assess", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["decision"] in ("APPROVE", "REVIEW", "DECLINE")
    assert "summary" in data
    assert data["applicant_id"] == "APP-TEST"


def test_assess_invalid_credit_score():
    payload = {
        "applicant_id": "APP-BAD",
        "credit_score": 999,   # out of range (max 850)
        "annual_income": 60000,
        "loan_amount": 10000,
        "employment": "Full-time",
    }
    r = client.post("/assess", json=payload)
    assert r.status_code == 422   # Pydantic validation error


def test_assessments_list():
    r = client.get("/assessments")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
