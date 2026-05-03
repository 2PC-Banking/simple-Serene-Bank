/**
 * 2PC Bank Participant – Frontend Logic
 * Communicates with the FastAPI backend to drive the Two-Phase Commit protocol.
 */

// ── API base resolution ───────────────────────────────────────────────────────
function resolveApiBase() {
    const { hostname, port, origin, protocol } = window.location;
    if (protocol === "file:") return "http://localhost:8001/api";
    if (
        (hostname === "localhost" || hostname === "127.0.0.1") &&
        port !== "" && port !== "80" && port !== "8080"
    ) {
        return "http://localhost:8001/api";
    }
    return `${origin}/api`;
}

const API_BASE  = resolveApiBase();
const HEALTH_URL = API_BASE.replace(/\/api\/?$/, "") + "/health";

// ── In-memory transaction state ───────────────────────────────────────────────
const txState = {
    status:   "IDLE",   // IDLE | PREPARED | COMMITTED | ABORTED
    vote:     null,     // YES | NO | null
    decision: null,     // COMMIT | ROLLBACK | null
    prepared: false,
};

// ── Utilities ─────────────────────────────────────────────────────────────────
function now() {
    return new Date().toLocaleTimeString("en-US", { hour12: false });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function formatMoney(amount) {
    return new Intl.NumberFormat("vi-VN", {
        style: "currency", currency: "VND", maximumFractionDigits: 0,
    }).format(amount);
}

// ── Toast notifications ───────────────────────────────────────────────────────
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
        el.style.opacity = "0";
        el.style.transition = "opacity .2s";
        setTimeout(() => el.remove(), 200);
    }, 3500);
}

// ── Generic API call ──────────────────────────────────────────────────────────
async function apiCall(url, method = "GET", body = null) {
    const options = {
        method,
        headers: { "Content-Type": "application/json" },
    };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    const raw = await response.text();
    const ct  = (response.headers.get("content-type") || "").toLowerCase();

    let data = null;
    if (raw) {
        try { data = JSON.parse(raw); } catch { data = null; }
    }

    if (!response.ok) {
        const detail = data?.detail || data?.message ||
            `HTTP ${response.status}${raw && !data ? ` – ${raw.slice(0, 120)}` : ""}`;
        throw new Error(detail);
    }

    if (data === null) {
        throw new Error(`Non-JSON response from ${url}`);
    }
    return data;
}

// ── Transaction ID generator ──────────────────────────────────────────────────
function generateTxId() {
    const ts   = Date.now().toString(36).toUpperCase();
    const rand = Math.random().toString(36).substring(2, 6).toUpperCase();
    document.getElementById("txId").value = `TX-${ts}-${rand}`;
}

// ── Read form inputs ──────────────────────────────────────────────────────────
function getBasePayload() {
    const txId      = document.getElementById("txId").value.trim();
    const accountId = document.getElementById("accountId").value;
    const operation = document.getElementById("operation").value;
    const amount    = parseFloat(document.getElementById("amount").value);

    if (!txId)          throw new Error("Please enter a Transaction ID");
    if (!accountId)     throw new Error("Please select an account");
    if (!amount || amount <= 0) throw new Error("Please enter a valid amount");

    return { txId, accountId, operation, amount };
}

// ── Timeline (flow steps) ─────────────────────────────────────────────────────
function addFlowStep(type, title, detail) {
    const container   = document.getElementById("flowContainer");
    const placeholder = container.querySelector(".timeline-empty");
    if (placeholder) placeholder.remove();

    const row = document.createElement("div");
    row.className = `flow-step ${type}`;
    row.innerHTML = `
        <span class="flow-time">${now()}</span>
        <div>
            <div class="flow-title">${title}</div>
            <div class="flow-detail">${detail}</div>
        </div>
    `;
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
}

function clearFlow() {
    document.getElementById("flowContainer").innerHTML =
        '<div class="timeline-empty">Run a transaction to see the step-by-step timeline.</div>';
}

// ── Participant state UI ──────────────────────────────────────────────────────
const STATE_CLASS = {
    IDLE:      "state-idle",
    PREPARED:  "state-prepared",
    COMMITTED: "state-committed",
    ABORTED:   "state-aborted",
};

function updateStateUI() {
    const statusEl   = document.getElementById("participantStatus");
    const voteEl     = document.getElementById("participantVote");
    const decisionEl = document.getElementById("coordinatorDecision");
    const stateMain  = document.getElementById("stateMain");
    const phase2Btn  = document.getElementById("btnExecutePhase2");

    statusEl.textContent   = txState.status;
    voteEl.textContent     = txState.vote     || "—";
    decisionEl.textContent = txState.decision || "WAITING";

    // Update state box styling
    stateMain.className = `state-main ${STATE_CLASS[txState.status] || "state-idle"}`;

    // Enable Phase 2 only when PREPARED
    phase2Btn.disabled = !txState.prepared;

    // Auto-fill Phase 2 decision based on vote (YES→COMMIT, NO→ROLLBACK)
    if (txState.vote === "YES") {
        document.getElementById("phase2Decision").value = "COMMIT";
    } else if (txState.vote === "NO") {
        document.getElementById("phase2Decision").value = "ROLLBACK";
    }
}

// ── Badges ────────────────────────────────────────────────────────────────────
function statusBadge(status) {
    const cls = {
        INIT:      "badge-init",
        PREPARED:  "badge-prepared",
        COMMITTED: "badge-committed",
        ABORTED:   "badge-aborted",
    }[status] || "badge-init";
    return `<span class="badge ${cls}">${status}</span>`;
}

function lockBadge(isLocked) {
    return isLocked
        ? '<span class="badge badge-locked">LOCKED</span>'
        : '<span class="badge badge-free">FREE</span>';
}

// ── Reset ─────────────────────────────────────────────────────────────────────
function resetTransaction() {
    txState.status   = "IDLE";
    txState.vote     = null;
    txState.decision = null;
    txState.prepared = false;

    document.getElementById("phase1ReceiveDelay").value   = "0";
    document.getElementById("phase1DropReceive").checked  = false;
    document.getElementById("phase1ForceNo").checked      = false;
    document.getElementById("phase1LoseVoteResponse").checked = false;
    document.getElementById("phase2ReceiveDelay").value   = "0";
    document.getElementById("phase2DropReceive").checked  = false;
    document.getElementById("phase2FailBeforeApply").checked = false;
    document.getElementById("phase2LoseAck").checked      = false;
    document.getElementById("phase2Decision").value       = "COMMIT";

    updateStateUI();
    clearFlow();
    generateTxId();
    showToast("Transaction state reset", "info");
}

// ── Health check ──────────────────────────────────────────────────────────────
async function checkHealth() {
    const statusEl = document.getElementById("serverStatus");
    const dot  = statusEl.querySelector(".status-dot");
    const text = statusEl.querySelector(".status-text");
    try {
        const data = await apiCall(HEALTH_URL);
        if (data.status === "healthy") {
            dot.className  = "status-dot online";
            text.textContent = "Bank Online";
        } else {
            dot.className  = "status-dot offline";
            text.textContent = "DB Disconnected";
        }
    } catch {
        dot.className  = "status-dot offline";
        text.textContent = "Server Offline";
    }
}

// ── Load accounts ─────────────────────────────────────────────────────────────
async function loadAccounts() {
    try {
        const result = await apiCall(`${API_BASE}/accounts`);
        const tbody  = document.getElementById("accountsBody");
        const rows   = result.data || [];

        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="table-empty">No accounts found</td></tr>';
            return;
        }

        tbody.innerHTML = rows.map(acc => `
            <tr>
                <td class="cell-mono">${acc.account_id}</td>
                <td>${acc.account_name}</td>
                <td class="cell-mono">${formatMoney(acc.balance)}</td>
                <td>${lockBadge(acc.is_locked)}</td>
            </tr>
        `).join("");

        const select    = document.getElementById("accountId");
        const currentVal = select.value;
        select.innerHTML =
            '<option value="">— Select account —</option>' +
            rows.map(acc =>
                `<option value="${acc.account_id}">${acc.account_id} – ${acc.account_name} (${formatMoney(acc.balance)})</option>`
            ).join("");
        if (currentVal) select.value = currentVal;
    } catch (err) {
        document.getElementById("accountsBody").innerHTML =
            `<tr><td colspan="4" class="table-empty" style="color:var(--danger)">${err.message}</td></tr>`;
    }
}

// ── Load transaction log ──────────────────────────────────────────────────────
async function loadTransactions() {
    try {
        const filter = document.getElementById("statusFilter").value;
        const url    = filter
            ? `${API_BASE}/transactions?status_filter=${filter}`
            : `${API_BASE}/transactions`;

        const result = await apiCall(url);
        const tbody  = document.getElementById("transactionsBody");

        if (!result.data?.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="table-empty">No transactions found</td></tr>';
            return;
        }

        tbody.innerHTML = result.data.map(tx => `
            <tr>
                <td class="cell-mono">${tx.id}</td>
                <td class="cell-mono">${tx.transaction_id}</td>
                <td class="cell-mono">${tx.account_id}</td>
                <td><strong>${tx.operation}</strong></td>
                <td class="cell-mono">${formatMoney(tx.amount)}</td>
                <td>${statusBadge(tx.status)}</td>
                <td class="cell-mono">${new Date(tx.created_at).toLocaleString("en-GB")}</td>
            </tr>
        `).join("");
    } catch (err) {
        document.getElementById("transactionsBody").innerHTML =
            `<tr><td colspan="7" class="table-empty" style="color:var(--danger)">${err.message}</td></tr>`;
    }
}

// ── Phase 1: PREPARE ──────────────────────────────────────────────────────────
async function runPrepare() {
    let base;
    try { base = getBasePayload(); } catch (err) {
        showToast(err.message, "error"); return;
    }

    // ① Drop simulation – pretend PREPARE was never received
    if (document.getElementById("phase1DropReceive").checked) {
        txState.status   = "IDLE";
        txState.vote     = null;
        txState.prepared = false;
        txState.decision = null;
        updateStateUI();
        addFlowStep("warning", "PREPARE Dropped", "Participant did not receive the PREPARE request (inbound dropped)");
        showToast("Inbound PREPARE dropped", "warning");
        return;
    }

    // ② Force-NO simulation – skip API, return NO immediately
    if (document.getElementById("phase1ForceNo").checked) {
        txState.status   = "IDLE";
        txState.vote     = "NO";
        txState.prepared = false;
        txState.decision = "ROLLBACK";
        updateStateUI();
        addFlowStep("error", "Vote NO Sent", "Participant received PREPARE but voted NO – coordinator will ROLLBACK");
        showToast("Vote NO simulated", "warning");
        return;
    }

    addFlowStep("prepare", "PREPARE Received", `TX: ${base.txId} · ${base.operation} ${formatMoney(base.amount)} on ${base.accountId}`);

    try {
        const response = await apiCall(`${API_BASE}/prepare`, "POST", {
            transaction_id:           base.txId,
            account_id:               base.accountId,
            operation:                base.operation,
            amount:                   base.amount,
            simulate_delay_ms:        Number(document.getElementById("phase1ReceiveDelay").value || 0),
            simulate_crash_before_vote: document.getElementById("phase1LoseVoteResponse").checked,
        });

        txState.vote     = response.vote;
        txState.status   = "PREPARED";
        txState.prepared = true;
        txState.decision = null;
        updateStateUI(); // also auto-fills Phase 2 decision = COMMIT

        addFlowStep("success", "Vote YES Sent", "Account locked, transaction log written → coordinator will COMMIT");
        showToast("Phase 1 complete – Vote YES", "success");

        await Promise.all([loadAccounts(), loadTransactions()]);
    } catch (err) {
        txState.vote     = null;
        txState.status   = "IDLE";
        txState.prepared = false;
        txState.decision = "ROLLBACK";
        updateStateUI();

        addFlowStep("error", "PREPARE Failed", err.message);
        showToast(`PREPARE failed: ${err.message}`, "error");
        await Promise.all([loadAccounts(), loadTransactions()]);
    }
}

// ── Phase 2: COMMIT / ROLLBACK ────────────────────────────────────────────────
async function runPhase2() {
    if (!txState.prepared) {
        showToast("Phase 1 must succeed before executing Phase 2", "warning");
        return;
    }

    const txId         = document.getElementById("txId").value.trim();
    const decision     = document.getElementById("phase2Decision").value;
    const delay        = Number(document.getElementById("phase2ReceiveDelay").value || 0);
    const failBefore   = document.getElementById("phase2FailBeforeApply").checked;
    const loseAck      = document.getElementById("phase2LoseAck").checked;

    // Drop simulation
    if (document.getElementById("phase2DropReceive").checked) {
        addFlowStep("warning", "Decision Dropped", `Participant did not receive the ${decision} decision`);
        showToast("Inbound decision dropped", "warning");
        return;
    }

    txState.decision = decision;
    updateStateUI();
    addFlowStep("decision", `Decision Received: ${decision}`, `Coordinator sent ${decision} for TX: ${txId}`);

    try {
        if (decision === "COMMIT") {
            const response = await apiCall(`${API_BASE}/commit`, "POST", {
                transaction_id:        txId,
                simulate_delay_ms:     delay,
                simulate_fail_before_apply: failBefore,
                simulate_crash:        loseAck,
            });

            txState.status   = "COMMITTED";
            txState.prepared = false;
            updateStateUI();

            addFlowStep(
                "success",
                "COMMIT Applied · ACK Sent",
                `Balance updated → ${formatMoney(response.new_balance)} · Account unlocked`
            );
            showToast("COMMIT successful", "success");
        } else {
            await apiCall(`${API_BASE}/rollback`, "POST", {
                transaction_id:           txId,
                simulate_delay_ms:        delay,
                simulate_crash_before_apply: false,
                simulate_crash_after_apply:  loseAck,
            });

            txState.status   = "ABORTED";
            txState.prepared = false;
            txState.vote     = "NO";
            updateStateUI();

            addFlowStep("warning", "ROLLBACK Applied · ACK Sent", "Transaction aborted · Account unlocked · Balance unchanged");
            showToast("ROLLBACK complete", "warning");
        }
    } catch (err) {
        addFlowStep("error", `${decision} Exception`, err.message);
        showToast(`${decision} failed: ${err.message}`, "error");
    }

    await Promise.all([loadAccounts(), loadTransactions()]);
}

// ── Auto-run full 2PC ─────────────────────────────────────────────────────────
async function executeAutoFlow() {
    await runPrepare();
    if (txState.prepared) {
        await sleep(400);
        await runPhase2();
    }
}

// ── Recovery actions ──────────────────────────────────────────────────────────
function showRecoveryResult(data) {
    const el = document.getElementById("recoveryResult");
    el.style.display = "block";
    el.textContent   = JSON.stringify(data, null, 2);
}

async function checkRecovery() {
    try {
        const result = await apiCall(`${API_BASE}/recovery/pending`);
        showRecoveryResult(result);
        showToast(`${result.pending_count} pending transaction(s)`, "info");
    } catch (err) { showToast(err.message, "error"); }
}

async function autoRollbackExpired() {
    try {
        const result = await apiCall(`${API_BASE}/recovery/auto-rollback-expired`, "POST");
        showRecoveryResult(result);
        showToast(`Auto-rolled back: ${result.rolled_back_count}`, result.rolled_back_count ? "warning" : "success");
        await Promise.all([loadAccounts(), loadTransactions()]);
    } catch (err) { showToast(err.message, "error"); }
}

async function forceRollbackAll() {
    try {
        const result = await apiCall(`${API_BASE}/recovery/force-rollback`, "POST");
        showRecoveryResult(result);
        showToast(`Force-rolled back: ${result.rolled_back_count}`, "warning");
        await Promise.all([loadAccounts(), loadTransactions()]);
    } catch (err) { showToast(err.message, "error"); }
}

async function cleanupLocks() {
    try {
        const result = await apiCall(`${API_BASE}/recovery/cleanup-locks`, "POST");
        showRecoveryResult(result);
        showToast(`Cleaned ${result.cleaned_count} stale lock(s)`, "success");
        await loadAccounts();
    } catch (err) { showToast(err.message, "error"); }
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    generateTxId();
    updateStateUI();
    await checkHealth();
    await Promise.all([loadAccounts(), loadTransactions()]);

    // Periodic health check every 30 s
    setInterval(checkHealth, 30_000);
});
