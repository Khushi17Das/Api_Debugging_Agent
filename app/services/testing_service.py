import time
import json
from typing import Optional, Dict, Any
import httpx
from app.schemas import TestResultResponse
from app.utils.helpers import validate_test_url


class TestingService:
    """Executes controlled HTTP requests against target APIs and collects telemetry."""

    @staticmethod
    def test_endpoint(
        endpoint: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        expected_status: Optional[int] = None,
        timeout: float = 10.0,
    ) -> TestResultResponse:
        """
        Executes a guarded HTTP request to test an API endpoint.
        Returns status code, response payload, headers, timing, and pass/fail evaluation.
        """
        if endpoint and endpoint.strip().startswith("/"):
            endpoint = f"http://127.0.0.1:8000{endpoint.strip()}"

        is_valid, validation_error = validate_test_url(endpoint)
        if not is_valid:
            return TestResultResponse(
                endpoint=endpoint or "",
                method=method.upper(),
                status_code=None,
                response_body=None,
                response_headers=None,
                response_time_ms=None,
                pass_fail="ERROR",
                error_detail=f"Security/Validation Error: {validation_error}",
            )

        method_upper = method.upper().strip()
        request_headers = headers or {}
        
        request_kwargs: Dict[str, Any] = {
            "headers": request_headers,
            "timeout": timeout,
            "follow_redirects": True,
        }

        if body and method_upper in ("POST", "PUT", "PATCH", "DELETE"):
            body_str = body.strip()
            # If Content-Type isn't set and body looks like JSON, set JSON header
            if "content-type" not in {k.lower(): v for k, v in request_headers.items()}:
                if (body_str.startswith("{") and body_str.endswith("}")) or (body_str.startswith("[") and body_str.endswith("]")):
                    request_headers["Content-Type"] = "application/json"
            request_kwargs["content"] = body_str.encode("utf-8")

        start_time = time.perf_counter()
        try:
            with httpx.Client() as client:
                response = client.request(method_upper, endpoint, **request_kwargs)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            resp_text = response.text
            if len(resp_text) > 8000:
                resp_text = resp_text[:8000] + "\n... [truncated for display]"

            resp_headers = {str(k): str(v) for k, v in response.headers.items()}

            if expected_status is not None:
                pass_fail = "PASS" if response.status_code == expected_status else "FAIL"
            else:
                pass_fail = "PASS" if 200 <= response.status_code < 400 else "FAIL"

            return TestResultResponse(
                endpoint=endpoint,
                method=method_upper,
                status_code=response.status_code,
                response_body=resp_text,
                response_headers=resp_headers,
                response_time_ms=elapsed_ms,
                pass_fail=pass_fail,
                error_detail=None if pass_fail == "PASS" else f"Expected status {expected_status or '2xx/3xx'}, got {response.status_code}",
            )

        except httpx.ConnectTimeout:
            return TestResultResponse(
                endpoint=endpoint,
                method=method_upper,
                status_code=None,
                response_body=None,
                response_headers=None,
                response_time_ms=None,
                pass_fail="ERROR",
                error_detail=f"Connection timed out after {timeout} seconds.",
            )
        except httpx.ConnectError as e:
            return TestResultResponse(
                endpoint=endpoint,
                method=method_upper,
                status_code=None,
                response_body=None,
                response_headers=None,
                response_time_ms=None,
                pass_fail="ERROR",
                error_detail=f"Connection failed: Could not connect to host ({str(e)}).",
            )
        except Exception as e:
            return TestResultResponse(
                endpoint=endpoint,
                method=method_upper,
                status_code=None,
                response_body=None,
                response_headers=None,
                response_time_ms=None,
                pass_fail="ERROR",
                error_detail=f"Request failed with error: {str(e)}",
            )
