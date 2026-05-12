function resolveApiBase() {
    const { hostname, port, origin, protocol } = window.location;
    if (protocol === "file:") return "http://localhost:8001/api";
    if ((hostname === "localhost" || hostname === "127.0.0.1") && port && port !== "80" && port !== "8080") {
        return "http://localhost:8001/api";
    }
    return `${origin}/api`;
}

const API_BASE = resolveApiBase();
const HEALTH_URL = API_BASE.replace(/\/api\/?$/, "") + "/health";
const SERVICES_URL = `${API_BASE}/interbank/services`;

let currentTransactionId = null;
let lastPayload = null;

const scenarioText = {
    happy_path: "Happy path: Serene debit và Family credit đều vote YES, coordinator quyết định COMMIT.",
    invalid_destination: "Family account không tồn tại. Family vote NO, coordinator ROLLBACK toàn bộ.",
    insufficient_source_balance: "Serene không đủ số dư. Serene vote NO, coordinator ROLLBACK.",
    source_prepare_crash: "Coordinator gọi PREPARE nhưng Serene giả lập crash trước khi trả vote.",
    source_commit_ack_lost: "Serene đã COMMIT nhưng giả lập mất ACK, coordinator sẽ thấy IN_DOUBT.",
    source_commit_fail_before_apply: "Serene lỗi trước khi áp dụng COMMIT, coordinator sẽ thấy IN_DOUBT.",
    source_rollback_ack_lost: "Family vote NO để rollback, Serene rollback nhưng mất ACK nên coordinator có thể IN_DOUBT.",
    coordinator_crash: "Giả lập Serene delay 15 giây. Hãy tắt Java Coordinator trong lúc hệ thống đang chờ để test lỗi sập Coordinator.",
};

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function now() {
    return new Date().toLocaleTimeString("vi-VN", { hour12: false });
}

function formatMoney(amount) {
    return new Intl.NumberFormat("vi-VN", {
        style: "currency",
        currency: "VND",
        maximumFractionDigits: 0,
    }).format(Number(amount || 0));
}

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

async function apiCall(url, method = "GET", body = null) {
    const options = { method, headers: { "Content-Type": "application/json" } };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    const raw = await response.text();
    let data = null;
    if (raw) {
        try { data = JSON.parse(raw); } catch { data = raw; }
    }
    if (!response.ok) {
        const detail = typeof data === "object" ? data?.detail || data?.message || JSON.stringify(data) : data;
        const err = new Error(detail || `HTTP ${response.status}`);
        err.payload = data;
        throw err;
    }
    return data;
}

function generateClientTxId() {
    const ts = Date.now().toString(36).toUpperCase();
    const rand = Math.random().toString(36).slice(2, 8).toUpperCase();
    return `WEB-SERENE-${ts}-${rand}`;
}

function statusBadge(status) {
    const value = String(status || "UNKNOWN").toUpperCase();
    const cls = {
        COMMITTED: "badge-committed",
        DONE: "badge-committed",
        ACK: "badge-committed",
        YES: "badge-committed",
        ABORTED: "badge-aborted",
        NO: "badge-aborted",
        NACK: "badge-aborted",
        IN_DOUBT: "badge-prepared",
        PROCESSING_PREPARE: "badge-prepared",
        PROCESSING_DECISION: "badge-prepared",
        PREPARED: "badge-prepared",
        LOCKED: "badge-locked",
        FREE: "badge-free",
    }[value] || "badge-init";
    return `<span class="badge ${cls}">${escapeHtml(value)}</span>`;
}

function lockBadge(isLocked) {
    return statusBadge(isLocked ? "LOCKED" : "FREE");
}

function setServiceChip(id, online, text) {
    const chip = document.getElementById(id);
    if (!chip) return;
    const dot = chip.querySelector(".status-dot");
    const label = chip.querySelector("span:last-child");
    dot.className = `status-dot ${online ? "online" : "offline"}`;
    label.textContent = text;
}

function addFlowStep(type, title, detail) {
    const container = document.getElementById("flowContainer");
    const placeholder = container.querySelector(".timeline-empty");
    if (placeholder) placeholder.remove();
    const row = document.createElement("div");
    row.className = `flow-step ${type}`;
    row.innerHTML = `
        <span class="flow-time">${now()}</span>
        <div>
            <div class="flow-title">${escapeHtml(title)}</div>
            <div class="flow-detail">${escapeHtml(detail)}</div>
        </div>
    `;
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
}

function clearFlow() {
    document.getElementById("flowContainer").innerHTML =
        '<div class="timeline-empty">Các bước gửi qua coordinator sẽ hiện ở đây.</div>';
}

function applyScenarioDefaults() {
    const scenario = document.getElementById("scenario").value;
    document.getElementById("scenarioHelp").textContent = scenarioText[scenario] || "";

    if (scenario === "invalid_destination" || scenario === "source_rollback_ack_lost") {
        document.getElementById("toAccount").value = "FAMILY_NOT_FOUND";
        document.getElementById("amount").value = "50000";
    } else if (scenario === "insufficient_source_balance") {
        document.getElementById("toAccount").value = "1000000002";
        document.getElementById("amount").value = "999999999";
    } else {
        document.getElementById("toAccount").value = "1000000002";
        document.getElementById("amount").value = "50000";
    }
}

function resetFormDefaults() {
    document.getElementById("scenario").value = "happy_path";
    document.getElementById("note").value = "Serene web 2PC demo";
    applyScenarioDefaults();
}

function renderResult(payload) {
    lastPayload = payload;
    currentTransactionId = payload?.transactionId || payload?.transaction_id || currentTransactionId;
    document.getElementById("refreshStatusBtn").disabled = !currentTransactionId;
    document.getElementById("retryDecisionBtn").disabled = payload?.status !== "IN_DOUBT" || !currentTransactionId;
    document.getElementById("rawJson").textContent = JSON.stringify(payload, null, 2);

    const participants = Array.isArray(payload?.participants) ? payload.participants : [];
    const participantHtml = participants.length
        ? participants.map(p => `
            <tr>
                <td>${escapeHtml(p.name || p.Name || "-")}</td>
                <td>${escapeHtml(p.operation || p.Operation || "-")}</td>
                <td>${statusBadge(p.prepareVote || p.PrepareVote || "UNKNOWN")}</td>
                <td>${statusBadge(p.decisionAck || p.DecisionAck || "UNKNOWN")}</td>
                <td>${escapeHtml(p.lastError || p.LastError || "")}</td>
            </tr>
        `).join("")
        : '<tr><td colspan="5" class="table-empty">Chưa có participant state.</td></tr>';

    document.getElementById("resultPanel").innerHTML = `
        <div class="result-grid">
            <div><span>Status</span>${statusBadge(payload?.status)}</div>
            <div><span>Phase</span>${statusBadge(payload?.phase)}</div>
            <div><span>Decision</span><strong>${escapeHtml(payload?.decision || "-")}</strong></div>
            <div><span>Số tiền</span><strong>${formatMoney(payload?.amount)}</strong></div>
            <div><span>Tài khoản nguồn (DEBIT)</span><strong>${escapeHtml(payload?.fromAccount || "-")}</strong></div>
            <div><span>Tài khoản nhận (CREDIT)</span><strong>${escapeHtml(payload?.toAccount || "-")}</strong></div>
        </div>
        <div class="table-wrap participant-table">
            <table>
                <thead>
                    <tr>
                        <th>Participant</th>
                        <th>Thao tác</th>
                        <th>Vote</th>
                        <th>ACK</th>
                        <th>Lỗi</th>
                    </tr>
                </thead>
                <tbody>${participantHtml}</tbody>
            </table>
        </div>
    `;
}

function toggleRawJson() {
    const el = document.getElementById("rawJson");
    el.style.display = el.style.display === "none" ? "block" : "none";
}

async function submitTransfer(event) {
    event.preventDefault();
    const button = document.getElementById("submitTransfer");
    button.disabled = true;

    const scenario = document.getElementById("scenario").value;
    let toAccount = document.getElementById("toAccount").value.trim();
    let amount = Number(document.getElementById("amount").value || 0);

    if (scenario === "invalid_destination" || scenario === "source_rollback_ack_lost") {
        toAccount = "FAMILY_NOT_FOUND";
        amount = 50000;
    } else if (scenario === "insufficient_source_balance") {
        toAccount = "1000000002";
        amount = 999999999;
    }

    const payload = {
        clientTxId: generateClientTxId(),
        fromAccount: document.getElementById("fromAccount").value,
        toAccount,
        amount,
        note: document.getElementById("note").value,
        destinationBank: "Family Banking",
        scenario,
    };

    if (!payload.fromAccount || !payload.toAccount || payload.amount <= 0) {
        showToast("Vui lòng nhập đủ tài khoản và số tiền hợp lệ.", "warning");
        button.disabled = false;
        return;
    }

    try {
        addFlowStep("prepare", "Gửi yêu cầu sang Serene gateway", "Gateway sẽ gọi Java Coordinator, không gọi trực tiếp participant từ browser.");
        const response = await apiCall(`${API_BASE}/interbank/transfer-2pc`, "POST", payload);
        renderResult(response);
        addFlowStep(response.success ? "success" : "warning", "Coordinator trả trạng thái", `${response.status || "UNKNOWN"} / ${response.phase || "-"} / ${response.decision || "-"}`);
        showToast(`Coordinator: ${response.status || "UNKNOWN"}`, response.success ? "success" : "warning");
        await refreshAll(false);
    } catch (err) {
        renderResult({ status: "ERROR", phase: "-", decision: "-", amount: payload.amount, fromAccount: payload.fromAccount, toAccount: payload.toAccount, error: err.message, payload: err.payload });
        addFlowStep("error", "Gửi coordinator thất bại", err.message);
        showToast(err.message, "error");
    } finally {
        button.disabled = false;
    }
}

async function refreshCoordinatorStatus() {
    if (!currentTransactionId) return;
    try {
        const response = await apiCall(`${API_BASE}/interbank/transfer-2pc/${currentTransactionId}`);
        renderResult({
            ...response,
            fromAccount: lastPayload?.fromAccount,
            toAccount: lastPayload?.toAccount,
            amount: response.amount ?? lastPayload?.amount,
        });
        addFlowStep("decision", "Cập nhật trạng thái coordinator", `${response.status || "UNKNOWN"} / ${response.phase || "-"}`);
        await refreshAll(false);
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function retryDecision() {
    if (!currentTransactionId) return;
    try {
        const response = await apiCall(`${API_BASE}/interbank/transfer-2pc/${currentTransactionId}/retry-decision`, "POST");
        renderResult({
            ...response,
            fromAccount: lastPayload?.fromAccount,
            toAccount: lastPayload?.toAccount,
            amount: response.amount ?? lastPayload?.amount,
        });
        addFlowStep("decision", "Retry decision", `${response.status || "UNKNOWN"} / ${response.phase || "-"}`);
        await refreshAll(false);
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function checkHealth() {
    const statusEl = document.getElementById("serverStatus");
    const dot = statusEl.querySelector(".status-dot");
    const text = statusEl.querySelector(".status-text");
    try {
        const data = await apiCall(HEALTH_URL);
        if (data.status === "healthy") {
            dot.className = "status-dot online";
            text.textContent = "Serene gateway online";
            setServiceChip("serviceSerene", true, "online");
        } else {
            dot.className = "status-dot offline";
            text.textContent = "Serene gateway lỗi";
            setServiceChip("serviceSerene", false, "lỗi");
        }
    } catch {
        dot.className = "status-dot offline";
        text.textContent = "Serene gateway offline";
        setServiceChip("serviceSerene", false, "offline");
    }

    try {
        const data = await apiCall(SERVICES_URL);
        const services = data.services || [];
        const coordinator = services.find(s => s.name === "Java Coordinator");
        const family = services.find(s => s.name === "Family Backend");
        if (coordinator) {
            setServiceChip("serviceCoordinator", coordinator.online, coordinator.online ? "online" : "offline");
        }
        if (family) {
            setServiceChip("serviceFamily", family.online, family.online ? "online" : "offline");
        }
    } catch {
        setServiceChip("serviceCoordinator", false, "không kiểm tra được");
        setServiceChip("serviceFamily", false, "không kiểm tra được");
    }
}

async function loadAccounts() {
    try {
        const result = await apiCall(`${API_BASE}/accounts`);
        const rows = result.data || [];
        const tbody = document.getElementById("accountsBody");
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="table-empty">Chưa có tài khoản.</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map(acc => `
            <tr>
                <td class="cell-mono">${escapeHtml(acc.account_id)}</td>
                <td>${escapeHtml(acc.account_name)}</td>
                <td class="cell-mono">${formatMoney(acc.balance)}</td>
                <td>${lockBadge(acc.is_locked)}</td>
            </tr>
        `).join("");

        const select = document.getElementById("fromAccount");
        const current = select.value;
        select.innerHTML = rows.map(acc =>
            `<option value="${escapeHtml(acc.account_id)}">${escapeHtml(acc.account_id)} - ${escapeHtml(acc.account_name)} (${formatMoney(acc.balance)})</option>`
        ).join("");
        select.value = current || "ACC001";
    } catch (err) {
        document.getElementById("accountsBody").innerHTML =
            `<tr><td colspan="4" class="table-empty" style="color:var(--danger)">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function loadTransactions() {
    try {
        const filter = document.getElementById("statusFilter").value;
        const url = filter ? `${API_BASE}/transactions?status_filter=${filter}` : `${API_BASE}/transactions`;
        const result = await apiCall(url);
        const rows = result.data || [];
        const tbody = document.getElementById("transactionsBody");
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="table-empty">Chưa có transaction.</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map(tx => `
            <tr>
                <td class="cell-mono">${escapeHtml(tx.account_id)}</td>
                <td><strong>${escapeHtml(tx.operation)}</strong></td>
                <td class="cell-mono">${formatMoney(tx.amount)}</td>
                <td>${statusBadge(tx.status)}</td>
                <td class="cell-mono">${new Date(tx.created_at).toLocaleString("vi-VN")}</td>
                <td>
                    ${tx.operation === 'CREDIT' ? `<button class="btn btn-ghost btn-sm" onclick="fetchPassiveCoordinatorStatus('${tx.transaction_id}')">Xem Coordinator</button>` : '-'}
                </td>
            </tr>
        `).join("");
    } catch (err) {
        document.getElementById("transactionsBody").innerHTML =
            `<tr><td colspan="6" class="table-empty" style="color:var(--danger)">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function refreshAll(includeHealth = true) {
    const tasks = [loadAccounts(), loadTransactions(), loadReceiverSimulation()];
    if (includeHealth) tasks.push(checkHealth());
    await Promise.allSettled(tasks);
}

async function loadReceiverSimulation() {
    try {
        const config = await apiCall(`${API_BASE}/simulation/receiver`);
        let scenario = 'happy_path';
        if (config.simulate_prepare_crash_before_vote) scenario = 'prepare_crash';
        else if (config.simulate_commit_fail_before_apply) scenario = 'commit_fail';
        else if (config.simulate_commit_crash) scenario = 'commit_crash';
        else if (config.simulate_rollback_crash_after_apply) scenario = 'rollback_crash';
        else if (config.simulate_delay_ms === 15000) scenario = 'coordinator_crash';
        document.getElementById('receiverScenario').value = scenario;
    } catch (err) {
        console.error("Failed to load receiver simulation config:", err);
    }
}

async function saveReceiverSimulation() {
    const scenario = document.getElementById('receiverScenario').value;
    const config = {
        simulate_prepare_crash_before_vote: scenario === 'prepare_crash',
        simulate_commit_fail_before_apply: scenario === 'commit_fail',
        simulate_commit_crash: scenario === 'commit_crash',
        simulate_rollback_crash_after_apply: scenario === 'rollback_crash',
        simulate_delay_ms: scenario === 'coordinator_crash' ? 15000 : 0
    };
    try {
        await apiCall(`${API_BASE}/simulation/receiver`, "POST", config);
        showToast("Đã lưu cấu hình giả lập nhận tiền", "success");
    } catch (err) {
        showToast("Lỗi khi lưu cấu hình: " + err.message, "error");
    }
}

async function fetchPassiveCoordinatorStatus(transactionId) {
    try {
        addFlowStep("prepare", "Kiểm tra Coordinator", "Đang fetch trạng thái từ Java Coordinator...");
        currentTransactionId = transactionId;
        const response = await apiCall(`${API_BASE}/interbank/transfer-2pc/${transactionId}`);
        renderResult(response);
        addFlowStep("decision", "Cập nhật trạng thái coordinator", `${response.status || "UNKNOWN"} / ${response.phase || "-"}`);
        document.getElementById("resultPanel").scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
        showToast("Không thể fetch Coordinator: " + err.message, "error");
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    document.getElementById("transferForm").addEventListener("submit", submitTransfer);
    resetFormDefaults();
    await refreshAll(true);
    setInterval(checkHealth, 30_000);
});
