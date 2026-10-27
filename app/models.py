from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from app.database import Base


class DebugSession(Base):
    """Represents an API debugging analysis, suggested fix, and test verification."""
    __tablename__ = "debug_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    endpoint = Column(String(500), nullable=True)
    method = Column(String(10), nullable=True, default="GET")
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    request_body = Column(Text, nullable=True)
    response_body = Column(Text, nullable=True)
    logs = Column(Text, nullable=True)
    backend_code = Column(Text, nullable=True)

    # Mode & Status ("diagnosis" / "smart_fallback" ; "diagnosed" / "needs_more_evidence")
    mode = Column(String(50), nullable=False, default="diagnosis")
    status = Column(String(50), nullable=False, default="diagnosed")
    confidence = Column(String(20), nullable=False, default="medium")  # high, medium, low
    safe_fix_mode = Column(String(50), nullable=False, default="SAFE TO SUGGEST")  # SAFE TO SUGGEST, NEEDS MORE EVIDENCE

    error_summary = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    evidence = Column(Text, nullable=True)  # JSON-encoded array of evidence strings

    suggested_fix = Column(Text, nullable=True)
    before_code = Column(Text, nullable=True)
    after_code = Column(Text, nullable=True)
    fixed_code = Column(Text, nullable=True)
    additional_notes = Column(Text, nullable=True)

    # Smart Fallback Mode specific fields
    confirmed_facts = Column(Text, nullable=True)      
    likely_causes = Column(Text, nullable=True)         
    possible_causes = Column(Text, nullable=True)      
    assumptions = Column(Text, nullable=True)          
    missing_information = Column(Text, nullable=True)  
    safe_next_steps = Column(Text, nullable=True)       

    # Testing and Verification
    test_request = Column(Text, nullable=True)          
    test_result = Column(Text, nullable=True)           
    verification_result = Column(Text, nullable=True)  
    is_resolved = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Converts model instance to dictionary with decoded JSON fields."""
        def safe_json_load(val, default):
            if not val:
                return default
            try:
                return json.loads(val)
            except Exception:
                return default

        return {
            "id": self.id,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "request_body": self.request_body,
            "response_body": self.response_body,
            "logs": self.logs,
            "backend_code": self.backend_code,
            "mode": self.mode,
            "status": self.status,
            "confidence": self.confidence,
            "safe_fix_mode": self.safe_fix_mode,
            "error_summary": self.error_summary,
            "root_cause": self.root_cause,
            "evidence": safe_json_load(self.evidence, []),
            "suggested_fix": self.suggested_fix,
            "before_code": self.before_code,
            "after_code": self.after_code,
            "fixed_code": self.fixed_code,
            "additional_notes": self.additional_notes,
            "confirmed_facts": safe_json_load(self.confirmed_facts, []),
            "likely_causes": safe_json_load(self.likely_causes, []),
            "possible_causes": safe_json_load(self.possible_causes, []),
            "assumptions": safe_json_load(self.assumptions, []),
            "missing_information": safe_json_load(self.missing_information, []),
            "safe_next_steps": safe_json_load(self.safe_next_steps, []),
            "test_request": safe_json_load(self.test_request, None),
            "test_result": safe_json_load(self.test_result, None),
            "verification_result": safe_json_load(self.verification_result, None),
            "is_resolved": self.is_resolved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
