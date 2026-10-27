
// Auto-detect Backend API Host:
// When running on Live Server (port 5500) or another dev port, target FastAPI on port 8000.
// When running directly through FastAPI on port 8000, use relative paths.
const API_BASE = (window.location.protocol === "file:" || (window.location.port && window.location.port !== "8000"))
  ? `http://${window.location.hostname || "127.0.0.1"}:8000`
  : "";

let currentAnalysisSession = null;
let currentHistoryFilter = "all";
let allHistoryRecords = [];

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initNavigation();
  loadDashboardData();
  checkSystemHealth();
});

function initTheme() {
  const saved = localStorage.getItem("app_theme") || "light";
  setTheme(saved);
}

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("app_theme", theme);

  const icon = document.getElementById("themeIcon");
  const label = document.getElementById("themeLabel");
  if (icon && label) {
    if (theme === "light") {
      icon.textContent = "🌙";
      label.textContent = "Dark";
    } else {
      icon.textContent = "☀️";
      label.textContent = "Light";
    }
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "light" ? "dark" : "light";
  setTheme(next);
  showToast(`Switched to ${next === "light" ? "Light" : "Dark"} theme!`);
}

function initNavigation() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetTab = tab.getAttribute("data-tab");
      switchTab(targetTab);
    });
  });
}

function switchTab(tabName) {
  // Update nav buttons
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabName);
  });

  // Update tab panes
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `tab-${tabName}`);
  });

  // Refresh data on tab switches
  if (tabName === "dashboard") {
    loadDashboardData();
  } else if (tabName === "history") {
    loadHistoryData();
  }
}

async function checkSystemHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (res.ok) {
      const data = await res.json();
      const badge = document.getElementById("systemStatusBadge");
      if (badge) {
        badge.innerHTML = `<span class="status-dot"></span> System Ready (${data.service})`;
      }
    }
  } catch (e) {
    const badge = document.getElementById("systemStatusBadge");
    if (badge) {
      badge.innerHTML = `<span class="status-dot" style="background-color: var(--accent-red)"></span> Offline`;
    }
  }
}

async function loadDashboardData() {
  try {
    const res = await fetch(`${API_BASE}/api/debug/stats`);
    if (!res.ok) return;
    const stats = await res.json();

    document.getElementById("statTotalSessions").textContent = stats.total_sessions || 0;
    document.getElementById("statSuccessfulFixes").textContent = stats.successful_fixes || 0;
    document.getElementById("statSmartFallback").textContent = stats.smart_fallback_cases || 0;
    document.getElementById("statSuccessRate").textContent = `${stats.success_rate_percent || 0}%`;

    renderRecentTable(stats.recent_sessions || []);
  } catch (err) {
    console.error("Failed to load dashboard stats:", err);
  }
}

function renderRecentTable(sessions) {
  const tbody = document.getElementById("dashboardRecentTable");
  if (!tbody) return;

  if (!sessions || sessions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No recent sessions found. Try debugging an API!</td></tr>`;
    return;
  }

  tbody.innerHTML = sessions.map((s) => {
    const isFallback = s.mode === "smart_fallback";
    const modeBadge = isFallback
      ? `<span class="badge badge-warning">Fallback</span>`
      : `<span class="badge badge-success">Diagnosed</span>`;

    const statusBadge = s.is_resolved
      ? `<span class="badge badge-success">Resolved</span>`
      : `<span class="badge" style="background: rgba(107, 114, 128, 0.2); color: #9ca3af;">Pending</span>`;

    const confClass = s.confidence === "high" ? "conf-high" : (s.confidence === "medium" ? "conf-medium" : "conf-low");

    return `
      <tr>
        <td><strong>#${s.id}</strong></td>
        <td>${modeBadge}</td>
        <td><code>${s.method || 'GET'} ${escapeHtml(s.endpoint || '/')}</code></td>
        <td>${s.status_code ? `<span class="badge" style="background: var(--bg-tertiary)">${s.status_code}</span>` : '-'}</td>
        <td><span class="confidence-tag ${confClass}">${s.confidence.toUpperCase()}</span></td>
        <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(s.error_summary || s.error_message || '-')}</td>
        <td>${statusBadge}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="viewSessionDetails(${s.id})">Inspect</button>
        </td>
      </tr>
    `;
  }).join("");
}

const PRESETS = {
  fallback_500: {
    endpoint: "http://127.0.0.1:8000/api/orders",
    method: "POST",
    statusCode: 500,
    errorMessage: "500 Internal Server Error",
    requestBody: JSON.stringify({ order_id: 8192, amount: 49.99 }, null, 2),
    responseBody: JSON.stringify({ detail: "Internal Server Error" }, null, 2),
    logs: "",
    backendCode: ""
  },
  pydantic_422: {
    endpoint: "http://127.0.0.1:8000/api/sample/users",
    method: "POST",
    statusCode: 422,
    errorMessage: "value is not a valid email address",
    requestBody: JSON.stringify({ name: "Jane Doe", email: "invalid-email-address" }, null, 2),
    responseBody: JSON.stringify({ detail: [{ loc: ["body", "email"], msg: "value is not a valid email address", type: "value_error" }] }, null, 2),
    logs: "",
    backendCode: "@app.post('/api/sample/users')\ndef create_user(user: CreateUserModel):\n    return {'status': 'success', 'user': user.dict()}"
  },
  db_operational: {
    endpoint: "http://127.0.0.1:8000/api/sample/database-fail",
    method: "POST",
    statusCode: 500,
    errorMessage: "500 Internal Server Error",
    requestBody: "",
    responseBody: JSON.stringify({ detail: "sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file" }),
    logs: "Traceback (most recent call last):\n  File '/app/routes.py', line 54, in db_action\n    conn = engine.connect()\nsqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file",
    backendCode: "def get_db():\n    engine = create_engine(DATABASE_URL)\n    return engine.connect()"
  },
  auth_401: {
    endpoint: "http://127.0.0.1:8000/api/sample/protected",
    method: "GET",
    statusCode: 401,
    errorMessage: "Missing Authorization header. Expected 'Bearer <token>'.",
    requestBody: "",
    responseBody: JSON.stringify({ detail: "Missing Authorization header. Expected 'Bearer <token>'." }),
    logs: "",
    backendCode: "@app.get('/api/sample/protected')\ndef get_protected_resource(authorization: Optional[str] = Header(None)):\n    if not authorization:\n        raise HTTPException(status_code=401)"
  },
  route_404: {
    endpoint: "http://127.0.0.1:8000/api/sample/users/999",
    method: "GET",
    statusCode: 404,
    errorMessage: "User with ID 999 does not exist in the database.",
    requestBody: "",
    responseBody: JSON.stringify({ detail: "User with ID 999 does not exist in the database." }),
    logs: "",
    backendCode: "@app.get('/api/sample/users/{user_id}')\ndef get_user(user_id: int):\n    if user_id != 1:\n        raise HTTPException(status_code=404)"
  },
  live_divide: {
    endpoint: "http://127.0.0.1:8000/api/sample/divide?a=10&b=0",
    method: "GET",
    statusCode: 500,
    errorMessage: "ZeroDivisionError: division by zero",
    requestBody: "",
    responseBody: JSON.stringify({ error: "ZeroDivisionError", message: "division by zero" }),
    logs: "Traceback (most recent call last):\n  File '/app/routes/sample_broken.py', line 45, in calculate_division\n    return {'result': a / b}\nZeroDivisionError: division by zero",
    backendCode: "@app.get('/api/sample/divide')\ndef calculate_division(a: float, b: float):\n    return {'result': a / b}"
  }
};

function loadPreset(key) {
  const p = PRESETS[key];
  if (!p) return;

  switchTab("debugger");

  document.getElementById("endpoint").value = p.endpoint;
  document.getElementById("method").value = p.method;
  document.getElementById("statusCode").value = p.statusCode || "";
  document.getElementById("errorMessage").value = p.errorMessage || "";
  document.getElementById("requestBody").value = p.requestBody || "";
  document.getElementById("responseBody").value = p.responseBody || "";
  document.getElementById("logs").value = p.logs || "";
  document.getElementById("backendCode").value = p.backendCode || "";

  showToast(`Loaded scenario preset: ${key}`);
}

function clearDebugForm() {
  document.getElementById("debugForm").reset();
  document.getElementById("analysisResultContent").classList.add("hidden");
  document.getElementById("analysisEmptyState").classList.remove("hidden");
  currentAnalysisSession = null;
  showToast("Cleared debugging form");
}


async function handleAnalyzeSubmit(e) {
  e.preventDefault();

  const endpoint = document.getElementById("endpoint").value.trim();
  const method = document.getElementById("method").value;
  const statusCode = parseInt(document.getElementById("statusCode").value) || null;
  const errorMessage = document.getElementById("errorMessage").value.trim();
  const requestBody = document.getElementById("requestBody").value.trim();
  const responseBody = document.getElementById("responseBody").value.trim();
  const logs = document.getElementById("logs").value.trim();
  const backendCode = document.getElementById("backendCode").value.trim();

  const payload = {
    endpoint: endpoint || null,
    method: method || "GET",
    status_code: statusCode,
    error_message: errorMessage || null,
    request_body: requestBody || null,
    response_body: responseBody || null,
    logs: logs || null,
    backend_code: backendCode || null,
  };

  document.getElementById("analysisEmptyState").classList.add("hidden");
  document.getElementById("analysisResultContent").classList.add("hidden");
  document.getElementById("analysisLoadingState").classList.remove("hidden");

  try {
    const res = await fetch(`${API_BASE}/api/debug/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Server returned ${res.status}`);
    }

    const data = await res.json();
    currentAnalysisSession = data;

    renderAnalysisResult(data);
    loadDashboardData(); // Refresh stats
  } catch (err) {
    showToast(`Analysis failed: ${err.message}`, "error");
    document.getElementById("analysisEmptyState").classList.remove("hidden");
  } finally {
    document.getElementById("analysisLoadingState").classList.add("hidden");
  }
}

function renderAnalysisResult(data) {
  const isFallback = data.mode === "smart_fallback";
  const container = document.getElementById("analysisResultContent");
  container.classList.remove("hidden");

  const banner = document.getElementById("resultBanner");
  banner.className = `result-banner ${isFallback ? 'banner-fallback' : 'banner-diagnosed'}`;

  const modeBadge = document.getElementById("badgeMode");
  modeBadge.textContent = isFallback ? "SMART FALLBACK" : "DIAGNOSED";
  modeBadge.className = `badge ${isFallback ? 'badge-warning' : 'badge-success'}`;

  const safeFixBadge = document.getElementById("badgeSafeFix");
  safeFixBadge.textContent = data.safe_fix_mode || (isFallback ? "NEEDS MORE EVIDENCE" : "SAFE TO SUGGEST");
  safeFixBadge.className = `badge ${data.safe_fix_mode === 'SAFE TO SUGGEST' ? 'badge-success' : 'badge-warning'}`;

  document.getElementById("resultTitle").textContent = isFallback
    ? "Smart Fallback Mode: Insufficient Evidence"
    : "Root Cause Identified";

  const confTag = document.getElementById("confidenceTag");
  confTag.textContent = (data.confidence || "MEDIUM").toUpperCase();
  confTag.className = `confidence-tag ${data.confidence === 'high' ? 'conf-high' : (data.confidence === 'low' ? 'conf-low' : 'conf-medium')}`;

  document.getElementById("sessionNumber").textContent = data.session_id ? `#${data.session_id}` : 'Local';
  document.getElementById("errorSummaryText").textContent = data.error_summary || "No summary provided.";

  const fallbackSec = document.getElementById("smartFallbackSection");
  const diagnosedSec = document.getElementById("diagnosedSection");

  if (isFallback) {
    diagnosedSec.classList.add("hidden");
    fallbackSec.classList.remove("hidden");

    renderList("confirmedFactsList", data.confirmed_facts || ["Status code provided"]);
    renderList("assumptionsList", data.assumptions || ["Assuming server crashed on unhandled exception"]);

    renderList("likelyCausesList", data.likely_causes || ["Unhandled server runtime exception"]);
    renderList("possibleCausesList", data.possible_causes || ["Gateway timeout or third party outage"]);

    renderList("missingInfoList", data.missing_information || ["Full server traceback", "Backend route handler code"]);
    renderList("safeNextStepsList", data.safe_next_steps || ["Check server terminal logs for Python traceback"]);
  } else {
    fallbackSec.classList.add("hidden");
    diagnosedSec.classList.remove("hidden");

    document.getElementById("rootCauseText").textContent = data.root_cause || "Root cause identified.";

    const evList = document.getElementById("evidenceList");
    evList.innerHTML = (data.evidence || []).map((e) => `<li>✔ ${escapeHtml(e)}</li>`).join("");

    document.getElementById("recommendedFixText").textContent = data.suggested_fix || "Apply suggested code update.";

    document.getElementById("codeBeforeBlock").textContent = data.before_code || "// Broken snippet not available";
    document.getElementById("codeAfterBlock").textContent = data.fixed_code || data.after_code || "// Corrected snippet";

    const notesBox = document.getElementById("additionalNotesBox");
    if (data.additional_notes) {
      notesBox.classList.remove("hidden");
      document.getElementById("additionalNotesText").textContent = data.additional_notes;
    } else {
      notesBox.classList.add("hidden");
    }
  }

  document.getElementById("verificationResultCard").classList.add("hidden");
}

function renderList(elemId, items) {
  const el = document.getElementById(elemId);
  if (!el) return;
  if (!items || items.length === 0) {
    el.innerHTML = `<li>None specified.</li>`;
    return;
  }
  el.innerHTML = items.map((i) => `<li>${escapeHtml(i)}</li>`).join("");
}

function transferToTester() {
  if (!currentAnalysisSession) return;
  switchTab("tester");

  const ep = document.getElementById("endpoint").value;
  const meth = document.getElementById("method").value;
  const reqBody = currentAnalysisSession.test_request?.body || document.getElementById("requestBody").value;

  document.getElementById("testUrl").value = ep || "http://127.0.0.1:8000/api/sample/users";
  document.getElementById("testMethod").value = meth || "GET";
  document.getElementById("testBody").value = reqBody || "";
  document.getElementById("testExpectedStatus").value = 200;

  showToast("Transferred session parameters to Endpoint Tester");
}

async function triggerFixVerification() {
  if (!currentAnalysisSession) {
    showToast("No active debugging session to verify", "error");
    return;
  }

  const endpoint = document.getElementById("endpoint").value.trim();
  const method = document.getElementById("method").value;
  const body = currentAnalysisSession.test_request?.body || document.getElementById("requestBody").value;
  const beforeStatus = parseInt(document.getElementById("statusCode").value) || null;

  showToast("Executing automated fix verification...");

  try {
    const reqHeaders = currentAnalysisSession.test_request?.headers || (body ? { "Content-Type": "application/json" } : {});

    const res = await fetch(`${API_BASE}/api/debug/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentAnalysisSession.session_id,
        endpoint: endpoint || null,
        method: method || "GET",
        headers: reqHeaders,
        body: body || null,
        before_status: beforeStatus,
        expected_status: null,
      }),
    });

    if (!res.ok) throw new Error("Verification request failed");
    const result = await res.json();

    const card = document.getElementById("verificationResultCard");
    card.classList.remove("hidden");

    document.getElementById("verifyBeforeStatus").textContent = `Before: ${result.before_status || 'Failure'}`;
    document.getElementById("verifyAfterStatus").textContent = `After: ${result.after_status || 'N/A'}`;
    document.getElementById("verificationResultMsg").textContent = result.result;

    const vBadge = document.getElementById("verificationBadge");
    if (result.is_resolved) {
      vBadge.className = "badge badge-success";
      vBadge.textContent = "VERIFIED RESOLVED";
    } else {
      vBadge.className = "badge badge-warning";
      vBadge.textContent = "UNVERIFIED / FAILING";
    }

    loadDashboardData(); 
  } catch (err) {
    showToast(`Verification error: ${err.message}`, "error");
  }
}

async function handleTestExecution(e) {
  e.preventDefault();

  const url = document.getElementById("testUrl").value.trim();
  const method = document.getElementById("testMethod").value;
  const expectedStatus = parseInt(document.getElementById("testExpectedStatus").value) || null;
  const headersRaw = document.getElementById("testHeaders").value.trim();
  const bodyRaw = document.getElementById("testBody").value.trim();

  let headers = {};
  if (headersRaw) {
    try {
      headers = JSON.parse(headersRaw);
    } catch {
      showToast("Headers must be valid JSON object", "error");
      return;
    }
  }

  const btn = document.getElementById("btnRunTest");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner" style="width:14px;height:14px;margin:0"></span> Running...`;

  try {
    const res = await fetch(`${API_BASE}/api/debug/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint: url,
        method: method,
        headers: headers,
        body: bodyRaw || null,
        expected_status: expectedStatus,
      }),
    });

    const data = await res.json();

    const container = document.getElementById("testOutputContainer");
    container.classList.remove("hidden");

    const passPill = document.getElementById("testSummaryPill");
    if (data.pass_fail === "PASS") {
      passPill.className = "badge badge-success";
      passPill.textContent = "PASS";
    } else if (data.pass_fail === "FAIL") {
      passPill.className = "badge badge-danger";
      passPill.textContent = "FAIL";
    } else {
      passPill.className = "badge badge-warning";
      passPill.textContent = "ERROR";
    }

    document.getElementById("testResponseTime").textContent = `${data.response_time_ms || 0} ms`;
    document.getElementById("testStatusCode").textContent = data.status_code || "N/A";
    document.getElementById("testResultMethod").textContent = data.method;
    document.getElementById("testResultEndpoint").textContent = data.endpoint;

    document.getElementById("testResponseBody").textContent = data.response_body || data.error_detail || "(empty)";
    document.getElementById("testResponseHeaders").textContent = data.response_headers
      ? JSON.stringify(data.response_headers, null, 2)
      : "(none)";

    showToast(`Test execution completed: ${data.pass_fail}`);
  } catch (err) {
    showToast(`Execution error: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Execute Endpoint Test`;
  }
}

function loadSampleTestTarget() {
  document.getElementById("testUrl").value = "http://127.0.0.1:8000/api/sample/users";
  document.getElementById("testMethod").value = "POST";
  document.getElementById("testExpectedStatus").value = 201;
  document.getElementById("testHeaders").value = JSON.stringify({ "Content-Type": "application/json" }, null, 2);
  document.getElementById("testBody").value = JSON.stringify({ name: "Alex Engineer", email: "alex@example.com" }, null, 2);
  showToast("Loaded sample valid user target");
}

function copyFixedCode() {
  const code = document.getElementById("codeAfterBlock").textContent;
  if (!code) return;
  navigator.clipboard.writeText(code).then(() => {
    showToast("Copied fixed snippet to clipboard!");
  });
}


async function loadHistoryData() {
  try {
    const res = await fetch(`${API_BASE}/api/debug/history?limit=100`);
    if (!res.ok) return;
    allHistoryRecords = await res.json();
    renderHistoryTable();
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

function filterHistory(mode) {
  currentHistoryFilter = mode;
  document.querySelectorAll(".history-controls .btn-pill").forEach((btn) => {
    btn.classList.toggle("active", btn.textContent.toLowerCase().includes(mode === "smart_fallback" ? "fallback" : mode));
  });
  renderHistoryTable();
}

function handleHistorySearch() {
  renderHistoryTable();
}

function renderHistoryTable() {
  const tbody = document.getElementById("historyTableBody");
  if (!tbody) return;

  const searchTerm = (document.getElementById("historySearchInput")?.value || "").toLowerCase().trim();

  let filtered = allHistoryRecords.filter((r) => {
    const matchesMode = currentHistoryFilter === "all" || r.mode === currentHistoryFilter;
    const matchesSearch = !searchTerm || (
      (r.endpoint && r.endpoint.toLowerCase().includes(searchTerm)) ||
      (r.error_summary && r.error_summary.toLowerCase().includes(searchTerm)) ||
      (r.error_message && r.error_message.toLowerCase().includes(searchTerm))
    );
    return matchesMode && matchesSearch;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-6">No matching sessions found in history.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((r) => {
    const isFallback = r.mode === "smart_fallback";
    const modeBadge = isFallback
      ? `<span class="badge badge-warning">Fallback</span>`
      : `<span class="badge badge-success">Diagnosed</span>`;

    const statusBadge = r.is_resolved
      ? `<span class="badge badge-success">Resolved</span>`
      : `<span class="badge" style="background: rgba(107, 114, 128, 0.2); color: #9ca3af;">Pending</span>`;

    const confClass = r.confidence === "high" ? "conf-high" : (r.confidence === "medium" ? "conf-medium" : "conf-low");
    const dateFormatted = r.created_at ? new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-';

    return `
      <tr>
        <td><strong>#${r.id}</strong></td>
        <td><small class="text-muted">${dateFormatted}</small></td>
        <td>${modeBadge}</td>
        <td><code>${r.method || 'GET'} ${escapeHtml(r.endpoint || '/')}</code></td>
        <td>${r.status_code ? `<span class="badge" style="background: var(--bg-tertiary)">${r.status_code}</span>` : '-'}</td>
        <td><span class="confidence-tag ${confClass}">${(r.confidence || 'MED').toUpperCase()}</span></td>
        <td style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(r.error_summary || r.error_message || '-')}</td>
        <td>${statusBadge}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="viewSessionDetails(${r.id})">Details</button>
          <button class="btn btn-outline btn-sm" style="color: var(--accent-red); margin-left: 4px;" onclick="deleteSession(${r.id})">&times;</button>
        </td>
      </tr>
    `;
  }).join("");
}

async function viewSessionDetails(id) {
  try {
    const res = await fetch(`${API_BASE}/api/debug/history/${id}`);
    if (!res.ok) throw new Error("Could not fetch session details");
    const session = await res.json();

    document.getElementById("modalSessionTitle").textContent = `Session #${session.id} - ${session.mode === 'smart_fallback' ? 'Smart Fallback' : 'Diagnosis'}`;

    const modalBody = document.getElementById("modalSessionBody");
    const isFallback = session.mode === "smart_fallback";

    modalBody.innerHTML = `
      <div class="result-banner ${isFallback ? 'banner-fallback' : 'banner-diagnosed'} mb-4">
        <div>
          <span class="badge ${isFallback ? 'badge-warning' : 'badge-success'}">${session.mode.toUpperCase()}</span>
          <span class="badge ${session.is_resolved ? 'badge-success' : 'badge-warning'}">${session.is_resolved ? 'RESOLVED' : 'UNRESOLVED'}</span>
          <h4 class="mt-2">${escapeHtml(session.error_summary || 'API Debugging Session')}</h4>
        </div>
      </div>

      <div class="form-row">
        <div class="metric-chip flex-1"><strong>Endpoint:</strong> <code>${session.method} ${escapeHtml(session.endpoint || '/')}</code></div>
        <div class="metric-chip flex-1"><strong>Status:</strong> ${session.status_code || 'N/A'}</div>
        <div class="metric-chip flex-1"><strong>Confidence:</strong> ${(session.confidence || '').toUpperCase()}</div>
      </div>

      ${session.root_cause ? `<div class="result-card mt-3"><h4>Root Cause</h4><p>${escapeHtml(session.root_cause)}</p></div>` : ''}

      ${session.suggested_fix ? `<div class="result-card mt-3"><h4>Suggested Fix</h4><p>${escapeHtml(session.suggested_fix)}</p></div>` : ''}

      ${session.fixed_code ? `
        <div class="result-card mt-3">
          <h4>Fixed Code Snippet</h4>
          <pre class="code-box"><code>${escapeHtml(session.fixed_code)}</code></pre>
        </div>
      ` : ''}

      ${isFallback ? `
        <div class="result-card mt-3">
          <h4>Missing Information Required</h4>
          <ul class="bullet-list">${(session.missing_information || []).map(m => `<li>${escapeHtml(m)}</li>`).join('')}</ul>
        </div>
      ` : ''}
    `;

    document.getElementById("modalLoadBtn").onclick = () => {
      closeSessionModal();
      loadSessionIntoForm(session);
    };

    document.getElementById("sessionModal").classList.remove("hidden");
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

function loadSessionIntoForm(session) {
  switchTab("debugger");
  document.getElementById("endpoint").value = session.endpoint || "";
  document.getElementById("method").value = session.method || "GET";
  document.getElementById("statusCode").value = session.status_code || "";
  document.getElementById("errorMessage").value = session.error_message || "";
  document.getElementById("requestBody").value = session.request_body || "";
  document.getElementById("responseBody").value = session.response_body || "";
  document.getElementById("logs").value = session.logs || "";
  document.getElementById("backendCode").value = session.backend_code || "";

  renderAnalysisResult(session);
  showToast(`Loaded Session #${session.id} into Debugger`);
}

async function deleteSession(id) {
  if (!confirm(`Delete debugging session #${id}?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/debug/history/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");
    showToast(`Session #${id} deleted`);
    loadHistoryData();
    loadDashboardData();
  } catch (err) {
    showToast(`Failed to delete: ${err.message}`, "error");
  }
}

function closeSessionModal(e) {
  if (e && e.target && e.target !== document.getElementById("sessionModal") && !e.target.classList.contains("modal-close")) return;
  document.getElementById("sessionModal").classList.add("hidden");
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type === 'error' ? 'badge-danger' : ''}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

function escapeHtml(text) {
  if (!text) return "";
  const map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  };
  return String(text).replace(/[&<>"']/g, (m) => map[m]);
}
