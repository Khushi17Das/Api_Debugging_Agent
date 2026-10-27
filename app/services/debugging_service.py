import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import DebugSession
from app.schemas import DebugInput, DebugAnalysisResponse
from app.services.llm_service import LLMService


class DebuggingService:
    """Orchestrates debugging workflow from evidence intake to database persistence."""

    def __init__(self):
        self.llm_service = LLMService()

    def process_and_diagnose(self, input_data: DebugInput, db: Session) -> DebugAnalysisResponse:
        """
        Executes analysis on supplied input data, enforces Smart Fallback if evidence
        is insufficient, persists the session in SQLite, and returns a structured response.
        """
        raw_result = self.llm_service.analyze(
            endpoint=input_data.endpoint,
            method=input_data.method,
            status_code=input_data.status_code,
            error_message=input_data.error_message,
            request_body=input_data.request_body,
            response_body=input_data.response_body,
            logs=input_data.logs,
            backend_code=input_data.backend_code,
        )

        mode = raw_result.get("mode", "diagnosis")
        status = raw_result.get("status", "diagnosed")
        confidence = raw_result.get("confidence", "medium")
        safe_fix_mode = raw_result.get("safe_fix_mode", "SAFE TO SUGGEST" if mode == "diagnosis" else "NEEDS MORE EVIDENCE")

        session_record = DebugSession(
            endpoint=input_data.endpoint,
            method=input_data.method or "GET",
            status_code=input_data.status_code,
            error_message=input_data.error_message,
            request_body=input_data.request_body,
            response_body=input_data.response_body,
            logs=input_data.logs,
            backend_code=input_data.backend_code,
            mode=mode,
            status=status,
            confidence=confidence,
            safe_fix_mode=safe_fix_mode,
            error_summary=raw_result.get("error_summary"),
            root_cause=raw_result.get("root_cause"),
            evidence=json.dumps(raw_result.get("evidence", [])),
            suggested_fix=raw_result.get("recommended_fix") or raw_result.get("suggested_fix"),
            before_code=raw_result.get("before_code"),
            after_code=raw_result.get("after_code"),
            fixed_code=raw_result.get("fixed_code"),
            additional_notes=raw_result.get("additional_notes"),
            confirmed_facts=json.dumps(raw_result.get("confirmed_facts", [])),
            likely_causes=json.dumps(raw_result.get("likely_causes", [])),
            possible_causes=json.dumps(raw_result.get("possible_causes", [])),
            assumptions=json.dumps(raw_result.get("assumptions", [])),
            missing_information=json.dumps(raw_result.get("missing_information", [])),
            safe_next_steps=json.dumps(raw_result.get("safe_next_steps", [])),
            test_request=json.dumps(raw_result.get("test_request")) if raw_result.get("test_request") else None,
            is_resolved=False,
        )

        db.add(session_record)
        db.commit()
        db.refresh(session_record)

        return DebugAnalysisResponse(
            session_id=session_record.id,
            mode=mode,
            status=status,
            confidence=confidence,
            safe_fix_mode=safe_fix_mode,
            error_summary=raw_result.get("error_summary", "Analysis completed."),
            root_cause=raw_result.get("root_cause"),
            evidence=raw_result.get("evidence", []),
            suggested_fix=raw_result.get("recommended_fix") or raw_result.get("suggested_fix"),
            fixed_code=raw_result.get("fixed_code"),
            before_code=raw_result.get("before_code"),
            after_code=raw_result.get("after_code"),
            additional_notes=raw_result.get("additional_notes"),
            test_request=raw_result.get("test_request"),
            confirmed_facts=raw_result.get("confirmed_facts", []),
            likely_causes=raw_result.get("likely_causes", []),
            possible_causes=raw_result.get("possible_causes", []),
            assumptions=raw_result.get("assumptions", []),
            missing_information=raw_result.get("missing_information", []),
            safe_next_steps=raw_result.get("safe_next_steps", []),
        )
