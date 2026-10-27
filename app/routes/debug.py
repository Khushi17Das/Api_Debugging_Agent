from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DebugSession
from app.schemas import (
    DebugInput,
    DebugAnalysisResponse,
    TestRequestInput,
    TestResultResponse,
    VerificationInput,
    VerificationResponse,
    StatsResponse,
    HistoryItem,
)
from app.services.debugging_service import DebuggingService
from app.services.testing_service import TestingService
from app.services.verification_service import VerificationService

router = APIRouter(prefix="/api/debug", tags=["Debugging"])
debugging_service = DebuggingService()


@router.post("/analyze", response_model=DebugAnalysisResponse, status_code=status.HTTP_200_OK)
def analyze_endpoint_error(input_data: DebugInput, db: Session = Depends(get_db)):
    """
    Analyzes API error evidence, decides between Diagnosed vs Smart Fallback Mode,
    saves the session to SQLite, and returns structured diagnosis and fix recommendations.
    """
    try:
        return debugging_service.process_and_diagnose(input_data, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during debugging analysis: {str(e)}",
        )


@router.post("/test", response_model=TestResultResponse, status_code=status.HTTP_200_OK)
def test_endpoint(test_input: TestRequestInput):
    """
    Executes a guarded HTTP request (GET, POST, PUT, PATCH, DELETE) against a target API,
    captures response time, headers, payload, and computes pass/fail status.
    """
    try:
        return TestingService.test_endpoint(
            endpoint=test_input.endpoint,
            method=test_input.method,
            headers=test_input.headers,
            body=test_input.body,
            expected_status=test_input.expected_status,
            timeout=test_input.timeout or 10.0,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test runner error: {str(e)}",
        )


@router.post("/verify", response_model=VerificationResponse, status_code=status.HTTP_200_OK)
def verify_endpoint_fix(verification_input: VerificationInput, db: Session = Depends(get_db)):
    """
    Validates a fix by re-testing the endpoint and comparing before vs after states.
    If the endpoint cannot be tested, returns 'Fix suggested, but automatic verification was not available.'
    """
    try:
        return VerificationService.verify_fix(verification_input, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification runner error: {str(e)}",
        )


@router.get("/stats", response_model=StatsResponse, status_code=status.HTTP_200_OK)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Retrieves aggregate analytics for the dashboard: total sessions, successful fixes,
    smart fallback occurrences, and recent activity.
    """
    total = db.query(DebugSession).count()
    smart_fallback_cases = db.query(DebugSession).filter(DebugSession.mode == "smart_fallback").count()
    diagnosed_cases = db.query(DebugSession).filter(DebugSession.mode == "diagnosis").count()
    successful_fixes = db.query(DebugSession).filter(DebugSession.is_resolved.is_(True)).count()
    unresolved_issues = total - successful_fixes

    success_rate = round((successful_fixes / total * 100), 1) if total > 0 else 0.0

    recent_records = (
        db.query(DebugSession)
        .order_by(DebugSession.created_at.desc())
        .limit(10)
        .all()
    )

    recent_items = [
        HistoryItem(
            id=r.id,
            endpoint=r.endpoint,
            method=r.method,
            status_code=r.status_code,
            error_message=r.error_message,
            mode=r.mode,
            status=r.status,
            confidence=r.confidence,
            error_summary=r.error_summary,
            root_cause=r.root_cause,
            is_resolved=r.is_resolved,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in recent_records
    ]

    return StatsResponse(
        total_sessions=total,
        successful_fixes=successful_fixes,
        unresolved_issues=unresolved_issues,
        smart_fallback_cases=smart_fallback_cases,
        diagnosed_cases=diagnosed_cases,
        success_rate_percent=success_rate,
        recent_sessions=recent_items,
    )
