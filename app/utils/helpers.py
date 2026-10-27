import json
import re
from urllib.parse import urlparse
from typing import Tuple, Dict, Any, List

BLOCKED_HOSTS = {
    "169.254.169.254",          
    "metadata.google.internal", 
    "100.100.100.200",         
    "0.0.0.0",
    "255.255.255.255",
}

GENERIC_ERROR_PHRASES = [
    "internal server error",
    "server error",
    "error",
    "something went wrong",
    "an error occurred",
    "failure",
    "failed",
    "unknown error",
    "bad request",
    "gateway timeout",
    "bad gateway",
    "service unavailable"
]


def validate_test_url(url: str) -> Tuple[bool, str]:
    """
    Validates target URL to prevent SSRF vulnerabilities and unsafe protocols.
    Allows testing localhost, 127.0.0.1, or remote HTTP/HTTPS APIs.
    """
    if not url or not isinstance(url, str):
        return False, "Target URL cannot be empty."

    url = url.strip()
    if url.startswith("/"):
        url = f"http://127.0.0.1:8000{url}"

    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "URL must start with http:// or https://"

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Malformed URL: {str(e)}"

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, "URL must contain a valid host."

    if hostname in BLOCKED_HOSTS:
        return False, f"Access to cloud metadata host '{hostname}' is forbidden for security."

    # Prevent link-local IP addresses (169.254.x.x)
    if hostname.startswith("169.254."):
        return False, "Access to link-local address space is forbidden."

    return True, ""


def evaluate_evidence_sufficiency(
    endpoint: str = None,
    method: str = None,
    status_code: int = None,
    error_message: str = None,
    request_body: str = None,
    response_body: str = None,
    logs: str = None,
    backend_code: str = None,
) -> Tuple[bool, str, List[str]]:
    """
    Determines whether there is sufficient empirical evidence to form a confident diagnosis,
    or whether the system must trigger Smart Fallback Mode.

    Returns:
        (is_sufficient, reason, confirmed_facts)
    """
    confirmed_facts: List[str] = []

    if endpoint:
        confirmed_facts.append(f"Target endpoint is '{method or 'GET'} {endpoint}'")
    if status_code:
        confirmed_facts.append(f"HTTP status code returned is {status_code}")
    if error_message:
        confirmed_facts.append(f"Reported error message: \"{error_message.strip()[:160]}\"")
    if request_body:
        confirmed_facts.append(f"Request payload provided ({len(request_body)} chars)")
    if logs:
        confirmed_facts.append(f"Server logs/traceback provided ({len(logs)} chars)")
    if backend_code:
        confirmed_facts.append(f"Backend handler code provided ({len(backend_code)} chars)")

    # Zero evidence check
    if not any([endpoint, status_code, error_message, request_body, logs, backend_code]):
        return False, "No diagnostic evidence was supplied.", confirmed_facts

    # Check for concrete evidence:
    has_concrete_logs = bool(logs and len(logs.strip()) > 15)
    # Concrete backend code provided
    has_concrete_code = bool(backend_code and len(backend_code.strip()) > 15)
    # Specific error message 
    err_str = (error_message or "").strip().lower()
    is_generic_msg = (not err_str) or any(err_str == g or err_str == f"{status_code} {g}" for g in GENERIC_ERROR_PHRASES)

    # Status codes with specific self-contained meaning:
    if status_code == 404 and endpoint:
        return True, "404 route error with known endpoint is diagnosable.", confirmed_facts

    if status_code == 405 and endpoint and method:
        return True, "405 method error with known endpoint and method is diagnosable.", confirmed_facts

    if status_code == 422 and (not is_generic_msg or request_body):
        return True, "422 validation error with message or request payload is diagnosable.", confirmed_facts

    if status_code in (401, 403) and not is_generic_msg:
        return True, "Authentication/authorization error has specific message.", confirmed_facts

    if has_concrete_logs:
        return True, "Sufficient server logs and stack traces are present for diagnosis.", confirmed_facts

    if has_concrete_code and (not is_generic_msg or request_body):
        return True, "Backend code combined with error or payload provides sufficient context.", confirmed_facts

    exception_indicators = [
        "operationalerror", "integrityerror", "syntaxerror", "typeerror", "keyerror",
        "valueerror", "zerodivisionerror", "attributeerror", "connectionrefused",
        "timeout", "validation", "pydantic", "jsondecodeerror", "not a valid email"
    ]
    if any(ind in err_str for ind in exception_indicators):
        return True, "Error message contains specific exception indicators.", confirmed_facts

    reason = (
        f"Only generic status code ({status_code or 'unspecified'}) or vague error message provided. "
        "Server traceback, error body, or backend code is missing."
    )
    return False, reason, confirmed_facts


def safe_json_parse(text: str) -> Any:
    """Attempts to parse JSON, returns raw text on failure."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return text
