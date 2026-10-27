from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DebugInput(BaseModel):
    """Input payload for API error debugging and analysis."""
    endpoint: Optional[str] = Field(None, description="API URL or route path (e.g. /api/users)")
    method: Optional[str] = Field("GET", description="HTTP Method (GET, POST, PUT, DELETE, PATCH)")
    status_code: Optional[int] = Field(None, description="HTTP status code (e.g. 500, 422, 404)")
    error_message: Optional[str] = Field(None, description="Error message received from API or client")
    request_body: Optional[str] = Field(None, description="Request body payload sent to endpoint")
    response_body: Optional[str] = Field(None, description="Response body returned by endpoint")
    logs: Optional[str] = Field(None, description="Server logs, traceback, or console output")
    backend_code: Optional[str] = Field(None, description="Relevant backend route handler or service code")


class TestRequestInput(BaseModel):
    """Input parameters to safely test an API endpoint."""
    endpoint: str = Field(..., description="Target endpoint URL (must start with http:// or https://)")
    method: str = Field("GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Request headers")
    body: Optional[str] = Field(None, description="Request body payload (JSON or string)")
    expected_status: Optional[int] = Field(None, description="Expected status code to assert against")
    timeout: Optional[float] = Field(10.0, ge=1.0, le=30.0, description="Request timeout in seconds")


class TestResultResponse(BaseModel):
    """Response returned from testing an endpoint."""
    endpoint: str
    method: str
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    response_headers: Optional[Dict[str, str]] = None
    response_time_ms: Optional[float] = None
    pass_fail: str = Field(..., description="'PASS', 'FAIL', or 'ERROR'")
    error_detail: Optional[str] = None


class VerificationInput(BaseModel):
    """Input payload for verifying a fix before and after."""
    session_id: Optional[int] = Field(None, description="Associated debug session ID")
    endpoint: Optional[str] = Field(None, description="Endpoint to re-test")
    method: str = Field("GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    body: Optional[str] = Field(None, description="Fixed request payload or test payload")
    before_status: Optional[int] = Field(None, description="Previous broken status code (e.g. 500)")
    expected_status: Optional[int] = Field(200, description="Expected status code after fix (default 200)")


class VerificationResponse(BaseModel):
    """Result of fix verification."""
    session_id: Optional[int] = None
    can_test: bool
    before_status: Optional[int] = None
    after_status: Optional[int] = None
    result: str = Field(..., description="Human-readable outcome of verification")
    is_resolved: bool = False
    test_result: Optional[TestResultResponse] = None


class DebugAnalysisResponse(BaseModel):
    """Unified structured response for both Diagnosed and Smart Fallback outcomes."""
    session_id: Optional[int] = None
    mode: str = Field(..., description="'diagnosis' or 'smart_fallback'")
    status: str = Field(..., description="'diagnosed' or 'needs_more_evidence'")
    confidence: str = Field(..., description="'high', 'medium', or 'low'")
    safe_fix_mode: str = Field(..., description="'SAFE TO SUGGEST' or 'NEEDS MORE EVIDENCE'")

    error_summary: str
    root_cause: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)

    # Diagnosed fields
    suggested_fix: Optional[str] = None
    fixed_code: Optional[str] = None
    before_code: Optional[str] = None
    after_code: Optional[str] = None
    additional_notes: Optional[str] = None
    test_request: Optional[Dict[str, Any]] = None

    # Smart Fallback specific fields
    confirmed_facts: List[str] = Field(default_factory=list)
    likely_causes: List[str] = Field(default_factory=list)
    possible_causes: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    safe_next_steps: List[str] = Field(default_factory=list)


class HistoryItem(BaseModel):
    """Summary representation of a debug session in history list."""
    id: int
    endpoint: Optional[str] = None
    method: Optional[str] = "GET"
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    mode: str
    status: str
    confidence: str
    error_summary: Optional[str] = None
    root_cause: Optional[str] = None
    is_resolved: bool = False
    created_at: Optional[str] = None


class StatsResponse(BaseModel):
    """Dashboard metrics aggregate."""
    total_sessions: int
    successful_fixes: int
    unresolved_issues: int
    smart_fallback_cases: int
    diagnosed_cases: int
    success_rate_percent: float
    recent_sessions: List[HistoryItem] = Field(default_factory=list)
