import json
from typing import Optional
from sqlalchemy.orm import Session
from app.models import DebugSession
from app.schemas import VerificationInput, VerificationResponse, TestResultResponse
from app.services.testing_service import TestingService


class VerificationService:
    """Validates suggested fixes by re-testing endpoints and updating resolution states."""

    @staticmethod
    def verify_fix(input_data: VerificationInput, db: Optional[Session] = None) -> VerificationResponse:
        """
        Re-tests the endpoint after a suggested fix.
        Only marks issue as resolved if live test executes and succeeds.
        Otherwise returns safe fallback message:
        'Fix suggested, but automatic verification was not available.'
        """
        session_record = None
        before_status = input_data.before_status

        if input_data.session_id and db:
            session_record = db.query(DebugSession).filter(DebugSession.id == input_data.session_id).first()
            if session_record and before_status is None:
                before_status = session_record.status_code

        # Check if endpoint URL is provided and testable
        endpoint = input_data.endpoint
        if not endpoint and session_record:
            endpoint = session_record.endpoint

        if endpoint and endpoint.strip().startswith("/"):
            endpoint = f"http://127.0.0.1:8000{endpoint.strip()}"

        if not endpoint or not (endpoint.startswith("http://") or endpoint.startswith("https://")):
            return VerificationResponse(
                session_id=input_data.session_id,
                can_test=False,
                before_status=before_status,
                after_status=None,
                result="Fix suggested, but automatic verification was not available.",
                is_resolved=False,
                test_result=None,
            )

        # Prepare headers
        headers = input_data.headers or {}
        if input_data.body and "content-type" not in {k.lower(): v for k, v in headers.items()}:
            headers["Content-Type"] = "application/json"

        # Run controlled test against endpoint
        test_result: TestResultResponse = TestingService.test_endpoint(
            endpoint=endpoint,
            method=input_data.method,
            headers=headers,
            body=input_data.body,
            expected_status=input_data.expected_status,
        )

        is_pass = (test_result.pass_fail == "PASS") or (test_result.status_code is not None and 200 <= test_result.status_code < 400)

        if is_pass:
            outcome_text = f"Issue appears resolved (Before: {before_status or 'Error'} -> After: {test_result.status_code} OK)"
            is_resolved = True
        else:
            outcome_text = f"Endpoint still failing (Status {test_result.status_code or 'Error'}, expected {input_data.expected_status or '2xx'})"
            is_resolved = False

        if session_record and db:
            session_record.is_resolved = is_resolved
            session_record.verification_result = json.dumps({
                "before_status": before_status,
                "after_status": test_result.status_code,
                "outcome": outcome_text,
                "is_resolved": is_resolved,
                "pass_fail": test_result.pass_fail,
            })
            db.commit()

        return VerificationResponse(
            session_id=input_data.session_id,
            can_test=True,
            before_status=before_status,
            after_status=test_result.status_code,
            result=outcome_text,
            is_resolved=is_resolved,
            test_result=test_result,
        )
