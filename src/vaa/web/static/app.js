const $ = (id) => document.getElementById(id);

const stateOrder = [
  "RECEIVED", "CONTRACT_CREATED", "GATHERING", "VERIFYING", "PROPOSAL_READY",
  "APPROVAL_PENDING", "APPROVED", "EXECUTING", "RECONCILING", "CONFIRMING", "COMPLETED"
];

let context = null;
let currentTask = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3500);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || body.detail || `HTTP ${response.status}`);
  return body;
}

async function loadContext() {
  context = await api("/api/demo/context");
  const health = await api("/healthz");
  $("provider-badge").textContent = `${health.llm_provider} analyzer · ${health.database}`;

  $("preset").innerHTML = context.presets
    .map((preset) => `<option value="${escapeHtml(preset.id)}">${escapeHtml(preset.label)}</option>`)
    .join("");
  $("user").innerHTML = context.users
    .map((user) => `<option value="${escapeHtml(user.id)}">${escapeHtml(user.name)} · ${escapeHtml(user.role)}</option>`)
    .join("");
  $("project").innerHTML = context.projects
    .map((project) => `<option value="${escapeHtml(project.id)}">${escapeHtml(project.id)} · ${escapeHtml(project.name)}</option>`)
    .join("");
  applyPreset(context.presets[0]);
}

function applyPreset(preset) {
  $("goal").value = preset.goal;
  $("requested-action").value = preset.requested_action;
  $("failure-mode").value = preset.failure_mode;
  $("user").value = "alice";
  $("project").value = "P-1024";
}

function badgeClass(value) {
  if (["COMPLETED", "supported"].includes(value)) return "success";
  if (["FAILED", "REJECTED"].includes(value)) return "danger";
  if (["APPROVAL_PENDING", "conflicting", "RECONCILING"].includes(value)) return "warning";
  return "";
}

function renderTimeline(task) {
  let events = task.audit
    .filter((event) => event.event_type === "STATE_TRANSITION")
    .map((event) => event.payload.to);
  events = ["RECEIVED", ...events];
  const currentIndex = events.length - 1;
  $("timeline").innerHTML = events.map((state, index) => `
    <div class="timeline-step ${index < currentIndex ? "done" : "current"}">
      <div class="timeline-dot"></div>
      <div class="timeline-label">${escapeHtml(state.replaceAll("_", " "))}</div>
    </div>
  `).join("");
}

function renderContract(task) {
  const contract = task.contract;
  const rows = [
    ["Lane", contract.lane],
    ["Tenant / project", `${contract.tenant_id} / ${contract.project_id}`],
    ["Approval policy", contract.approval_policy],
    ["Evidence required", contract.required_evidence ? "Yes" : "No"],
    ["Budgets", `${contract.budgets.max_tool_calls} calls · ${contract.budgets.max_runtime_seconds}s · $${contract.budgets.max_cost_usd}`],
    ["Allowed tools", contract.allowed_tools.map((tool) => `<span class="tool-chip">${escapeHtml(tool)}</span>`).join("")],
  ];
  $("contract").innerHTML = rows.map(([key, value]) => `
    <div class="definition-row">
      <div class="definition-key">${escapeHtml(key)}</div>
      <div class="definition-value">${value}</div>
    </div>
  `).join("");
}

function renderVerification(task) {
  if (!task.verification) {
    $("verification").innerHTML = `<p class="muted">Verification has not run.</p>`;
    return;
  }
  $("verification").innerHTML = `
    <div class="check-list">
      ${Object.entries(task.verification.checks).map(([name, ok]) => `
        <div class="check-row">
          <span>${escapeHtml(name.replaceAll("_", " "))}</span>
          <strong class="check-icon ${ok ? "ok" : "fail"}">${ok ? "✓" : "✕"}</strong>
        </div>
      `).join("")}
    </div>
    ${task.verification.warnings.map((warning) => `<div class="security-banner">${escapeHtml(warning)}</div>`).join("")}
  `;
}

function renderEvidence(task) {
  if (!task.analysis) return;
  $("analysis-summary").innerHTML = `
    <strong>${escapeHtml(task.analysis.summary)}</strong>
    ${task.analysis.detected_security_signals.length ? `
      <div class="security-banner">Security signals: ${escapeHtml(task.analysis.detected_security_signals.join(", "))}</div>
    ` : ""}
  `;
  $("evidence").innerHTML = task.evidence.map((claim) => `
    <article class="evidence-card">
      <div class="panel-heading">
        <h4>${escapeHtml(claim.claim_text)}</h4>
        <span class="badge ${badgeClass(claim.status)}">${escapeHtml(claim.status)}</span>
      </div>
      <div class="value-row">
        ${claim.observed_values.map((value) => `<span class="value-pill">${escapeHtml(value)}</span>`).join("")}
      </div>
      ${claim.sources.map((source) => `
        <div class="source">
          <strong>${escapeHtml(source.title)} v${escapeHtml(source.version)}</strong><br>
          ${escapeHtml(source.section)} · ${escapeHtml(source.trust_level)}<br>
          “${escapeHtml(source.excerpt)}”
        </div>
      `).join("")}
    </article>
  `).join("");
}

function renderAction(task) {
  const area = $("action-area");
  if (task.receipt) {
    area.innerHTML = `
      <div class="receipt">
        <div class="eyebrow">ACTION RECEIPT</div>
        <div class="receipt-key">${escapeHtml(task.receipt.ticket_key)}</div>
        <p>External status: <strong>${escapeHtml(task.receipt.external_status)}</strong></p>
        <p>Postcondition confirmed: <strong>${task.receipt.confirmed ? "yes" : "no"}</strong></p>
        <p>Reconciled after timeout: <strong>${task.receipt.reconciled_after_timeout ? "yes" : "no"}</strong></p>
        <div class="hash">${escapeHtml(task.receipt.idempotency_key)}</div>
      </div>
    `;
    return;
  }
  if (!task.action_preview) {
    area.innerHTML = `<p class="muted">This task is read-only. No external side effect was proposed.</p>`;
    return;
  }

  area.innerHTML = `
    <div class="action-preview">
      <div><span class="badge warning">WRITE REQUIRES APPROVAL</span></div>
      <strong>${escapeHtml(task.action_preview.tool_name)}</strong>
      <span>${escapeHtml(task.action_preview.title)}</span>
      <div class="hash">Idempotency key: ${escapeHtml(task.action_preview.idempotency_key)}</div>
    </div>
    ${task.state === "APPROVAL_PENDING" ? `
      <div class="action-buttons">
        <button class="button success" id="approve-button">Approve and execute</button>
        <button class="button danger" id="reject-button">Reject</button>
      </div>
    ` : ""}
    ${task.state === "APPROVED" ? `
      <div class="security-banner">The workflow is safely paused after approval. Resume it to prove durable state recovery.</div>
      <div class="action-buttons"><button class="button primary" id="resume-button">Resume workflow</button></div>
    ` : ""}
    ${task.state === "REJECTED" ? `<div class="security-banner">Action rejected. No ticket was created.</div>` : ""}
  `;

  $("approve-button")?.addEventListener("click", () => decide("approve"));
  $("reject-button")?.addEventListener("click", () => decide("reject"));
  $("resume-button")?.addEventListener("click", () => decide("resume"));
}

function renderAudit(task) {
  $("audit").innerHTML = task.audit.map((event) => `
    <div class="audit-event">
      <div class="audit-type">${escapeHtml(event.event_type)}</div>
      <div class="audit-payload">${escapeHtml(JSON.stringify(event.payload, null, 2))}</div>
      <div class="audit-time">${escapeHtml(new Date(event.created_at).toLocaleTimeString())}</div>
    </div>
  `).join("");
}

function renderTask(task) {
  currentTask = task;
  $("empty-state").classList.add("hidden");
  $("task-view").classList.remove("hidden");
  $("task-id").textContent = task.id;
  $("lane-badge").textContent = task.lane;
  $("lane-badge").className = "badge";
  $("state-badge").textContent = task.state;
  $("state-badge").className = `badge ${badgeClass(task.state)}`;
  renderTimeline(task);
  renderContract(task);
  renderVerification(task);
  renderEvidence(task);
  $("rfi-subject").textContent = task.analysis?.rfi_subject || "No proposal";
  $("rfi-draft").textContent = task.analysis?.rfi_draft || "";
  renderAction(task);
  renderAudit(task);
}

async function runTask() {
  const button = $("run-button");
  button.disabled = true;
  button.textContent = "Running…";
  try {
    const task = await api("/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        user_id: $("user").value,
        project_id: $("project").value,
        goal: $("goal").value,
        requested_action: $("requested-action").value,
        failure_mode: $("failure-mode").value,
      }),
    });
    renderTask(task);
    showToast(`Created ${task.id}`);
  } catch (error) {
    showToast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Run controlled workflow";
  }
}

async function decide(action) {
  try {
    const task = await api(`/api/tasks/${currentTask.id}/${action}`, {
      method: "POST",
      body: JSON.stringify({ actor_id: "alice", comment: `Demo ${action}` }),
    });
    renderTask(task);
    showToast(`${action} completed`);
  } catch (error) {
    showToast(error.message);
  }
}

$("preset").addEventListener("change", () => {
  applyPreset(context.presets.find((preset) => preset.id === $("preset").value));
});
$("run-button").addEventListener("click", runTask);
$("reset-button").addEventListener("click", async () => {
  await api("/api/demo/reset", { method: "POST", body: "{}" });
  currentTask = null;
  $("task-view").classList.add("hidden");
  $("empty-state").classList.remove("hidden");
  showToast("Demo data reset");
});

loadContext().catch((error) => showToast(error.message));
