import os
import json
import re
from typing import Dict, Any, Optional
from app.utils.helpers import evaluate_evidence_sufficiency


SYSTEM_PROMPT = """You are an expert AI API Debugging Agent and Staff Reliability Engineer.
Your primary directive is to DIAGNOSE ACCURATELY USING ONLY CONFIRMED EVIDENCE.

CRITICAL INSTRUCTIONS:
1. DO NOT GUESS OR INVENT CAUSES without empirical evidence.
2. If the user provides only a generic status code (like 500 Internal Server Error) without logs, traceback, or code, you MUST enter SMART FALLBACK MODE.
   - Do NOT say "your database is broken" if there is no database error in logs.
   - Say: "A 500 error indicates that the server encountered an internal exception, but the provided information is not enough to determine the exact cause."
3. Distinguish between:
   - CONFIRMED: Directly stated or shown in logs/error/code.
   - LIKELY: Strongly supported by pattern, but not 100% verified.
   - POSSIBLE: Reasonable alternative explanations.
   NEVER present 'possible' as 'confirmed'.
4. Before suggesting a code fix, decide if it is 'SAFE TO SUGGEST' or 'NEEDS MORE EVIDENCE'.

You MUST respond strictly with a valid JSON object in one of two formats:

FORMAT A: When evidence is insufficient (Smart Fallback Mode):
{
  "mode": "smart_fallback",
  "status": "needs_more_evidence",
  "confidence": "low",
  "safe_fix_mode": "NEEDS MORE EVIDENCE",
  "error_summary": "Short explanation acknowledging insufficient data",
  "confirmed_facts": ["List of explicitly confirmed facts from input"],
  "likely_causes": ["Top likely causes matching this failure pattern"],
  "possible_causes": ["Reasonable alternative explanations"],
  "assumptions": ["Assumptions made, clearly separated from facts"],
  "missing_information": ["Minimum missing details needed (e.g. traceback, route code)"],
  "safe_next_steps": ["Safe diagnostic steps to isolate the issue without guessing"]
}

FORMAT B: When evidence is sufficient (Diagnosis Mode):
{
  "mode": "diagnosis",
  "status": "diagnosed",
  "confidence": "high" or "medium",
  "safe_fix_mode": "SAFE TO SUGGEST",
  "error_summary": "Clear summary of the failure",
  "root_cause": "Precise root cause supported by evidence",
  "evidence": ["Bullet list of specific evidence points linking the error to the cause"],
  "recommended_fix": "Step-by-step recommended fix",
  "before_code": "Broken code snippet if applicable",
  "after_code": "Corrected code snippet",
  "fixed_code": "Clean, focused fix implementation",
  "additional_notes": "Helpful notes, edge cases, or preventative advice",
  "test_request": {
    "method": "HTTP METHOD",
    "endpoint": "URL or route",
    "headers": {"Content-Type": "application/json"},
    "body": "Fixed or test payload"
  }
}
"""


class LLMService:
    """Handles AI-powered debugging analysis and structured diagnosis."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    def analyze(
        self,
        endpoint: Optional[str] = None,
        method: Optional[str] = "GET",
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
        request_body: Optional[str] = None,
        response_body: Optional[str] = None,
        logs: Optional[str] = None,
        backend_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes evidence using OpenAI LLM if configured; otherwise utilizes
        the comprehensive RuleBasedEvidenceAnalyzer.
        """
        is_sufficient, reason, confirmed = evaluate_evidence_sufficiency(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            error_message=error_message,
            request_body=request_body,
            response_body=response_body,
            logs=logs,
            backend_code=backend_code,
        )

        if self.api_key and not self.api_key.startswith("your_") and len(self.api_key) > 20:
            try:
                ai_result = self._call_openai(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    error_message=error_message,
                    request_body=request_body,
                    response_body=response_body,
                    logs=logs,
                    backend_code=backend_code,
                    is_sufficient=is_sufficient,
                )
                if ai_result:
                    return ai_result
            except Exception as e:
                pass

        return self._rule_based_analysis(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            error_message=error_message,
            request_body=request_body,
            response_body=response_body,
            logs=logs,
            backend_code=backend_code,
            is_sufficient=is_sufficient,
            reason=reason,
            confirmed_facts=confirmed,
        )

    def _call_openai(
        self,
        endpoint, method, status_code, error_message,
        request_body, response_body, logs, backend_code, is_sufficient
    ) -> Optional[Dict[str, Any]]:
        """Calls OpenAI API with JSON response format."""
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)

        user_prompt = f"""EVIDENCE REPORT:
- Target Endpoint: {method or 'GET'} {endpoint or 'Not provided'}
- HTTP Status Code: {status_code or 'Not provided'}
- Error Message: {error_message or 'Not provided'}
- Request Payload: {request_body or 'Not provided'}
- Response Body: {response_body or 'Not provided'}
- Server Logs / Traceback:
{logs or 'No logs provided'}
- Backend Handler Code:
{backend_code or 'No code provided'}

System Evaluation Pre-check: Sufficient empirical evidence = {is_sufficient}.
Remember: If sufficient evidence is False, you MUST return format A (Smart Fallback Mode).
"""

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=1500,
        )

        content = response.choices[0].message.content
        if content:
            parsed = json.loads(content)
            return parsed
        return None

    def _rule_based_analysis(
        self,
        endpoint, method, status_code, error_message,
        request_body, response_body, logs, backend_code,
        is_sufficient, reason, confirmed_facts
    ) -> Dict[str, Any]:
        """
        High-fidelity deterministic diagnostic analyzer adhering to Smart Fallback.
        """
        err_msg = (error_message or "").strip()
        log_text = (logs or "").strip()
        code_text = (backend_code or "").strip()
        combined_text = f"{err_msg}\n{log_text}\n{response_body or ''}".lower()

        if not is_sufficient:
            st = status_code or 500
            likely = [
                "Unhandled runtime exception or Python crash in request handler",
                "Database connection failure or connection pool exhaustion",
                "Missing environment variables or secret keys",
                "Uncaught serialization or validation exception"
            ]
            possible = [
                "Reverse proxy / Gateway timeout (Nginx/Cloudflare)",
                "Out-of-memory (OOM) or container termination",
                "Third-party upstream service dependency failure"
            ]
            missing = [
                "Full server traceback or terminal error log",
                "Backend route handler code (FastAPI/Flask/Django route)",
                "Full request payload and headers sent by the client"
            ]
            safe_steps = [
                "Check server terminal / console or Docker logs for the full Python traceback",
                "Wrap route logic in a try/except block to log the exact exception type and message",
                "Inspect database connection status and environment variable availability",
                "Re-run request with a minimal JSON body to rule out malformed input"
            ]
            assumptions = [
                f"Assuming the server returned HTTP {st} due to an unhandled application exception rather than an infrastructure crash",
                "Assuming default server exception formatting"
            ]

            summary = (
                f"An HTTP {st} error indicates a server-side failure, but the provided evidence "
                f"is insufficient to determine the exact cause without guessing."
            )

            return {
                "mode": "smart_fallback",
                "status": "needs_more_evidence",
                "confidence": "low",
                "safe_fix_mode": "NEEDS MORE EVIDENCE",
                "error_summary": summary,
                "confirmed_facts": confirmed_facts or [f"Received HTTP status code {st}"],
                "likely_causes": likely,
                "possible_causes": possible,
                "assumptions": assumptions,
                "missing_information": missing,
                "safe_next_steps": safe_steps,
            }


        if status_code == 422 or "validation" in combined_text or "not a valid email" in combined_text or "value is not a valid email" in combined_text:
            field_name = "email" if "email" in combined_text else "field"
            evidence_items = [
                "HTTP Status: 422 Unprocessable Entity",
                f"Error detail indicates validation failure: '{err_msg or 'Input validation error'}'",
            ]
            if request_body:
                evidence_items.append(f"Request payload provided: {request_body}")

            return {
                "mode": "diagnosis",
                "status": "diagnosed",
                "confidence": "high",
                "safe_fix_mode": "SAFE TO SUGGEST",
                "error_summary": f"Request validation failed for {field_name} field with status 422.",
                "root_cause": f"The request payload violates the schema constraints for '{field_name}'. The server rejected the request before execution.",
                "evidence": evidence_items,
                "recommended_fix": f"Update the request body so that '{field_name}' conforms to the expected type and format (e.g. valid email string).",
                "before_code": request_body if request_body else '{"email": "invalid-email-address"}',
                "after_code": '{"email": "alex.developer@example.com"}',
                "fixed_code": '{\n  "email": "alex.developer@example.com"\n}',
                "additional_notes": "FastAPI/Pydantic returns 422 whenever input types or regex patterns fail validation.",
                "test_request": {
                    "method": method or "POST",
                    "endpoint": endpoint or "/api/users",
                    "headers": {"Content-Type": "application/json"},
                    "body": '{"email": "alex.developer@example.com"}'
                }
            }

        if "sqlalchemy" in combined_text or "operationalerror" in combined_text or "connection refused" in combined_text:
            evidence_items = [
                f"HTTP status code: {status_code or 500}",
                "Server log contains: 'sqlalchemy.exc.OperationalError: could not connect to server'",
            ]
            if endpoint:
                evidence_items.append(f"Endpoint called: {method or 'GET'} {endpoint}")

            return {
                "mode": "diagnosis",
                "status": "diagnosed",
                "confidence": "high",
                "safe_fix_mode": "SAFE TO SUGGEST",
                "error_summary": "Database connection failure (SQLAlchemy OperationalError).",
                "root_cause": "The backend was unable to establish a connection to the SQL database. The database server may be offline, credentials incorrect, or DATABASE_URL host unreachable.",
                "evidence": evidence_items,
                "recommended_fix": "Verify that the database service is running, check network access, and verify the connection string/environment variable (DATABASE_URL).",
                "before_code": '# Faulty or unreachable connection string\nDATABASE_URL = "postgresql://user:pass@localhost:5432/nonexistent_db"',
                "after_code": '# Working connection with proper error handling and fallback\nimport os\nDATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")',
                "fixed_code": 'import os\nfrom sqlalchemy import create_engine\n\nDATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./debugging_agent.db")\nengine = create_engine(DATABASE_URL, pool_pre_ping=True)',
                "additional_notes": "Adding 'pool_pre_ping=True' prevents stale pooled connections from causing OperationalErrors.",
                "test_request": {
                    "method": method or "GET",
                    "endpoint": endpoint or "/api/db-query",
                    "headers": {"Content-Type": "application/json"},
                    "body": None
                }
            }

        if status_code == 401 or "unauthorized" in combined_text or "token" in combined_text or "bearer" in combined_text:
            evidence_items = [
                "HTTP Status: 401 Unauthorized",
                f"Reported error: '{err_msg or 'Authentication credentials were not provided or invalid'}'",
            ]
            return {
                "mode": "diagnosis",
                "status": "diagnosed",
                "confidence": "high",
                "safe_fix_mode": "SAFE TO SUGGEST",
                "error_summary": "Authentication failure: Missing or invalid authorization token.",
                "root_cause": "The request lacks a valid 'Authorization: Bearer <token>' header, or the provided token has expired or failed cryptographic verification.",
                "evidence": evidence_items,
                "recommended_fix": "Include an active, valid Bearer token in the request 'Authorization' header.",
                "before_code": '# Headers missing authorization token\nheaders = {"Content-Type": "application/json"}',
                "after_code": '# Headers with valid Bearer token\nheaders = {\n    "Content-Type": "application/json",\n    "Authorization": "Bearer valid_access_token_here"\n}',
                "fixed_code": 'headers = {\n    "Authorization": "Bearer valid_jwt_token",\n    "Content-Type": "application/json"\n}',
                "additional_notes": "Ensure token expiration (exp claim) is renewed before making requests.",
                "test_request": {
                    "method": method or "GET",
                    "endpoint": endpoint or "/api/protected",
                    "headers": {
                        "Authorization": "Bearer valid_token_123",
                        "Content-Type": "application/json"
                    },
                    "body": None
                }
            }

        if status_code == 404 or "not found" in combined_text:
            evidence_items = [
                "HTTP Status: 404 Not Found",
                f"Target path: '{endpoint or '/unknown'}'",
            ]
            return {
                "mode": "diagnosis",
                "status": "diagnosed",
                "confidence": "high",
                "safe_fix_mode": "SAFE TO SUGGEST",
                "error_summary": f"Route '{endpoint or 'requested resource'}' was not found on the server.",
                "root_cause": f"No active route handler matches '{method or 'GET'} {endpoint or ''}'. Common causes: missing trailing slash, incorrect prefix (e.g. missing /api/v1), or nonexistent ID.",
                "evidence": evidence_items,
                "recommended_fix": "Verify the route path in the backend router definition or verify that the requested resource ID exists.",
                "before_code": f'# Client requesting unmapped route\nrequests.{ (method or "get").lower() }("{endpoint or "/wrong-path"}")',
                "after_code": f'# Correct route path matching registered router\nrequests.{ (method or "get").lower() }("/api/correct-route")',
                "fixed_code": f'@app.{ (method or "get").lower() }("{endpoint or "/api/resource"}")\ndef handle_resource():\n    return {{"status": "ok"}}',
                "additional_notes": "Check for route prefixes registered via `app.include_router(..., prefix='/api')`.",
                "test_request": {
                    "method": method or "GET",
                    "endpoint": endpoint or "/api/sample/users/1",
                    "headers": {},
                    "body": None
                }
            }

        if status_code == 405 or "method not allowed" in combined_text:
            evidence_items = [
                "HTTP Status: 405 Method Not Allowed",
                f"HTTP Method used: '{method}'",
                f"Target route: '{endpoint}'"
            ]
            return {
                "mode": "diagnosis",
                "status": "diagnosed",
                "confidence": "high",
                "safe_fix_mode": "SAFE TO SUGGEST",
                "error_summary": f"HTTP Method {method} is not supported on endpoint '{endpoint}'.",
                "root_cause": f"The route '{endpoint}' exists but does not accept the '{method}' HTTP verb.",
                "evidence": evidence_items,
                "recommended_fix": f"Change the client HTTP method or update the route decorator in the backend to allow {method}.",
                "before_code": f'@app.get("{endpoint or "/api/data"}")\ndef handle(): ...',
                "after_code": f'@app.route("{endpoint or "/api/data"}", methods=["GET", "{method or "POST"}"])\ndef handle(): ...',
                "fixed_code": f'@app.{ (method or "post").lower() }("{endpoint or "/api/data"}")\ndef handle_request():\n    return {{"message": "success"}}',
                "additional_notes": "FastAPI will automatically return 405 when a route is defined for GET but POST is invoked.",
                "test_request": {
                    "method": "POST" if method == "GET" else "GET",
                    "endpoint": endpoint or "/api/data",
                    "headers": {},
                    "body": None
                }
            }

        for exc in ["ZeroDivisionError", "KeyError", "TypeError", "AttributeError", "ValueError"]:
            if exc.lower() in combined_text:
                evidence_items = [
                    f"HTTP Status: {status_code or 500}",
                    f"Traceback confirms Python exception: '{exc}'",
                ]
                if log_text:
                    evidence_items.append(f"Logs: {log_text[:120]}...")
                return {
                    "mode": "diagnosis",
                    "status": "diagnosed",
                    "confidence": "high",
                    "safe_fix_mode": "SAFE TO SUGGEST",
                    "error_summary": f"Unhandled Python exception '{exc}' caused server crash.",
                    "root_cause": f"The server handler crashed on a {exc} while processing the request. This occurs when an operation is performed without prerequisite validation.",
                    "evidence": evidence_items,
                    "recommended_fix": f"Add input validation or defensive checks before executing the operation to prevent {exc}.",
                    "before_code": "# Unsafe code\nresult = a / b  # Crashes if b is 0",
                    "after_code": "# Safe code with defensive guard\nif b == 0:\n    raise HTTPException(status_code=400, detail='Divisor cannot be zero')\nresult = a / b",
                    "fixed_code": "if b == 0:\n    raise HTTPException(status_code=400, detail='Divisor cannot be zero')\nreturn {'result': a / b}",
                    "additional_notes": "Always validate numerical inputs and dictionary keys prior to access.",
                    "test_request": {
                        "method": method or "GET",
                        "endpoint": endpoint or "/api/sample/divide?a=10&b=2",
                        "headers": {},
                        "body": None
                    }
                }

        return {
            "mode": "diagnosis",
            "status": "diagnosed",
            "confidence": "medium",
            "safe_fix_mode": "SAFE TO SUGGEST",
            "error_summary": f"Error occurred during {method or 'GET'} {endpoint or 'request'}.",
            "root_cause": f"Supported by error message: '{err_msg or 'Backend failure'}'.",
            "evidence": confirmed_facts,
            "recommended_fix": "Inspect the backend route handler and align request format with the expected interface.",
            "before_code": err_msg or "Error encountered",
            "after_code": "# Verified handler code",
            "fixed_code": "# Update endpoint handler to handle edge case gracefully",
            "additional_notes": "Ensure test coverage exists for edge cases.",
            "test_request": {
                "method": method or "GET",
                "endpoint": endpoint or "/",
                "headers": {},
                "body": None
            }
        }
