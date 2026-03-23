/**
 * Bank System 2PC Simulator - Frontend JavaScript
 * Bank 1: Real (với backend)
 * Bank 2: Simulated (frontend only)
 */

const API_BASE = window.location.protocol === "file:"
    ? "http://localhost:8001/api"
    : `${window.location.origin}/api`;

// =============================================
// 2PC State Management
// =============================================

const txState = {
    bank1: {
        status: 'IDLE',    // IDLE, PREPARED, COMMITTED, ABORTED
        vote: null,        // null, 'YES', 'NO'
        prepared: false
    },
    bank2: {
        status: 'IDLE',
        vote: null,
        prepared: false,
        // Simulated data
        simulatedBalance: 1000000,
        simulatedLocked: false
    },
    decision: null,  // null, 'COMMIT', 'ABORT'
    crashed: false   // Bank 2 crash simulation
};

// =============================================
// UI Update Functions
// =============================================

function updateAllUI() {
    updateBankUI('bank1');
    updateBankUI('bank2');
    updateCoordinatorUI();
    updateButtonStates();
    updateAccountDisplays();
}

function updateBankUI(bank) {
    const state = txState[bank];
    const panel = document.getElementById(`${bank}Panel`);
    const statusBadge = document.getElementById(`${bank}StatusBadge`);
    const voteBadge = document.getElementById(`${bank}VoteBadge`);

    // Update panel classes
    if (panel) {
        panel.classList.remove('state-idle', 'state-prepared', 'state-committed', 'state-aborted', 'state-crashed');
        if (txState.crashed && bank === 'bank2') {
            panel.classList.add('state-crashed');
        } else {
            panel.classList.add(`state-${state.status.toLowerCase()}`);
        }
    }

    // Update status badge
    if (statusBadge) {
        statusBadge.textContent = txState.crashed && bank === 'bank2' ? 'CRASHED' : state.status;
        statusBadge.className = 'status-badge ' + (txState.crashed && bank === 'bank2' ? 'crashed' : state.status.toLowerCase());
    }

    // Update vote badge
    if (voteBadge) {
        if (state.vote === 'YES') {
            voteBadge.textContent = '✅ YES';
            voteBadge.className = 'vote-badge yes';
        } else if (state.vote === 'NO') {
            voteBadge.textContent = '❌ NO';
            voteBadge.className = 'vote-badge no';
        } else {
            voteBadge.textContent = '—';
            voteBadge.className = 'vote-badge';
        }
    }

    // Update coordinator vote icons
    const voteIcon = document.getElementById(`voteIcon${bank.charAt(0).toUpperCase() + bank.slice(1)}`);
    const voteBox = document.getElementById(`voteBox${bank.charAt(0).toUpperCase() + bank.slice(1)}`);

    if (voteIcon && voteBox) {
        voteBox.classList.remove('voted-yes', 'voted-no', 'crashed');
        if (txState.crashed && bank === 'bank2') {
            voteIcon.textContent = '💥';
            voteBox.classList.add('crashed');
        } else if (state.vote === 'YES') {
            voteIcon.textContent = '✅';
            voteBox.classList.add('voted-yes');
        } else if (state.vote === 'NO') {
            voteIcon.textContent = '❌';
            voteBox.classList.add('voted-no');
        } else {
            voteIcon.textContent = '⏳';
        }
    }
}

function updateCoordinatorUI() {
    const decisionBox = document.getElementById('decisionBox');
    const decisionIcon = document.getElementById('decisionIcon');
    const decisionText = document.getElementById('decisionText');

    if (!decisionBox || !decisionIcon || !decisionText) return;

    decisionBox.classList.remove('commit', 'abort', 'waiting');

    const v1 = txState.bank1.vote;
    const v2 = txState.bank2.vote;

    if (txState.crashed) {
        decisionIcon.textContent = '💥';
        decisionText.textContent = 'Bank 2 Crashed!';
        decisionBox.classList.add('abort');
        txState.decision = 'ABORT';
    } else if (v1 === null && v2 === null) {
        decisionIcon.textContent = '🤔';
        decisionText.textContent = 'Waiting votes...';
        decisionBox.classList.add('waiting');
    } else if (v1 !== null && v2 !== null) {
        // Both voted
        if (v1 === 'YES' && v2 === 'YES') {
            decisionIcon.textContent = '✅';
            decisionText.textContent = 'COMMIT';
            decisionBox.classList.add('commit');
            txState.decision = 'COMMIT';
        } else {
            decisionIcon.textContent = '❌';
            decisionText.textContent = 'ABORT';
            decisionBox.classList.add('abort');
            txState.decision = 'ABORT';
        }
    } else {
        // Partial votes
        decisionIcon.textContent = '⏳';
        decisionText.textContent = 'Waiting...';
        decisionBox.classList.add('waiting');
    }
}

function updateButtonStates() {
    const btnCommit1 = document.getElementById('btnCommitBank1');
    const btnRollback1 = document.getElementById('btnRollbackBank1');
    const btnCommit2 = document.getElementById('btnCommitBank2');
    const btnRollback2 = document.getElementById('btnRollbackBank2');
    const btnPrepare1 = document.getElementById('btnPrepareBank1');
    const btnPrepare2 = document.getElementById('btnPrepareBank2');

    // Bank 1 buttons
    if (btnPrepare1) {
        btnPrepare1.disabled = txState.bank1.status !== 'IDLE';
    }
    if (btnCommit1) {
        btnCommit1.disabled = !(txState.bank1.status === 'PREPARED' && txState.decision === 'COMMIT');
    }
    if (btnRollback1) {
        btnRollback1.disabled = txState.bank1.status !== 'PREPARED';
    }

    // Bank 2 buttons
    if (btnPrepare2) {
        btnPrepare2.disabled = txState.bank2.status !== 'IDLE' || txState.crashed;
    }
    if (btnCommit2) {
        btnCommit2.disabled = !(txState.bank2.status === 'PREPARED' && txState.decision === 'COMMIT') || txState.crashed;
    }
    if (btnRollback2) {
        btnRollback2.disabled = txState.bank2.status !== 'PREPARED' || txState.crashed;
    }
}

function updateAccountDisplays() {
    const bank1Select = document.getElementById('bank1Account');
    const bank2Input = document.getElementById('bank2Account');
    const bank1Display = document.getElementById('bank1AccountDisplay');
    const bank2Display = document.getElementById('bank2AccountDisplay');

    if (bank1Select && bank1Display) {
        bank1Display.textContent = bank1Select.value || 'Chưa chọn';
    }
    if (bank2Input && bank2Display) {
        bank2Display.textContent = bank2Input.value || 'SIM-ACC-001';
    }
}

// =============================================
// Bank Log Functions
// =============================================

function addBankLog(bank, message, type = 'info') {
    const logContainer = document.getElementById(`${bank}Log`);
    if (!logContainer) return;

    // Remove placeholder
    const placeholder = logContainer.querySelector('.log-placeholder');
    if (placeholder) placeholder.remove();

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${type}`;
    logEntry.innerHTML = `
        <span class="log-time">${now()}</span>
        <span class="log-message">${message}</span>
    `;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function clearBankLogs() {
    ['bank1Log', 'bank2Log'].forEach(id => {
        const container = document.getElementById(id);
        if (container) {
            container.innerHTML = '<div class="log-placeholder">Waiting for actions...</div>';
        }
    });
}

// =============================================
// Utility Functions
// =============================================

function formatMoney(amount) {
    return new Intl.NumberFormat("vi-VN", {
        style: "currency",
        currency: "VND",
        maximumFractionDigits: 0,
    }).format(amount);
}

function now() {
    return new Date().toLocaleTimeString("vi-VN");
}

function generateTxId() {
    const ts = Date.now().toString(36).toUpperCase();
    const rand = Math.random().toString(36).substring(2, 6).toUpperCase();
    document.getElementById("txId").value = `TX-${ts}-${rand}`;
}

function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

async function apiCall(url, method = "GET", body = null) {
    const opts = {
        method,
        headers: { "Content-Type": "application/json" },
    };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(url, opts);
    const data = await res.json();

    if (!res.ok) {
        const detail = data.detail || JSON.stringify(data);
        throw new Error(detail);
    }
    return data;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// =============================================
// Reset Functions
// =============================================

function resetTransaction() {
    txState.bank1 = { status: 'IDLE', vote: null, prepared: false };
    txState.bank2 = { status: 'IDLE', vote: null, prepared: false, simulatedBalance: 1000000, simulatedLocked: false };
    txState.decision = null;
    txState.crashed = false;

    updateAllUI();
    clearFlow();
    clearBankLogs();
    generateTxId();

    // Reset checkboxes
    ['bank2SimulateDelay', 'bank2SimulateCrash', 'bank2SimulateCommitFail'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.checked = false;
    });

    showToast('Transaction reset', 'info');
}

// =============================================
// Flow Visualization
// =============================================

function addFlowStep(type, title, detail, source = null) {
    const container = document.getElementById("flowContainer");
    const placeholder = container.querySelector(".flow-placeholder");
    if (placeholder) placeholder.remove();

    const step = document.createElement("div");
    step.className = `flow-step flow-${type}`;

    const icons = {
        prepare: "📋",
        commit: "✅",
        rollback: "↩️",
        error: "❌",
        info: "ℹ️",
        crash: "💥",
        coordinator: "🎯"
    };

    const sourceLabel = source ? `<span class="flow-source">[${source}]</span>` : '';

    step.innerHTML = `
        <div class="flow-icon ${type}">${icons[type] || "•"}</div>
        <div class="flow-body">
            <div class="flow-title">${sourceLabel} ${title}</div>
            <div class="flow-detail">${detail}</div>
        </div>
        <div class="flow-time">${now()}</div>
    `;
    container.appendChild(step);
    container.scrollTop = container.scrollHeight;
}

function clearFlow() {
    document.getElementById("flowContainer").innerHTML =
        '<div class="flow-placeholder">Thực hiện giao dịch để xem flow 2PC</div>';
}

// =============================================
// Status Badge Helpers
// =============================================

function statusBadge(status) {
    const cls = {
        INIT: "badge-init",
        PREPARED: "badge-prepared",
        COMMITTED: "badge-committed",
        ABORTED: "badge-aborted",
    }[status] || "badge-init";
    return `<span class="badge ${cls}">${status}</span>`;
}

function lockBadge(isLocked) {
    return isLocked
        ? '<span class="badge badge-locked">🔒 Locked</span>'
        : '<span class="badge badge-free">🔓 Free</span>';
}

// =============================================
// Load Data
// =============================================

async function loadAccounts() {
    try {
        const data = await apiCall(`${API_BASE}/accounts`);
        const tbody = document.getElementById("accountsBody");

        if (!data.data || data.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading">Không có tài khoản</td></tr>';
            return;
        }

        tbody.innerHTML = data.data.map(acc => `
            <tr>
                <td><strong>${acc.account_id}</strong></td>
                <td>${acc.account_name}</td>
                <td class="money">${formatMoney(acc.balance)}</td>
                <td>${lockBadge(acc.is_locked)}</td>
                <td>${acc.locked_by_tx || "—"}</td>
            </tr>
        `).join("");

        populateAccountDropdowns(data.data);
    } catch (e) {
        document.getElementById("accountsBody").innerHTML =
            `<tr><td colspan="5" class="loading" style="color:var(--danger)">Lỗi: ${e.message}</td></tr>`;
    }
}

function populateAccountDropdowns(accounts) {
    const bank1Select = document.getElementById("bank1Account");
    const currentVal = bank1Select.value;

    const options = accounts.map(acc =>
        `<option value="${acc.account_id}">${acc.account_id} — ${acc.account_name} (${formatMoney(acc.balance)})</option>`
    ).join("");

    bank1Select.innerHTML = '<option value="">-- Chọn tài khoản --</option>' + options;

    if (currentVal) bank1Select.value = currentVal;
}

async function loadTransactions() {
    try {
        const statusFilter = document.getElementById("statusFilter").value;
        let url = `${API_BASE}/transactions`;
        if (statusFilter) url += `?status_filter=${statusFilter}`;

        const data = await apiCall(url);
        const tbody = document.getElementById("transactionsBody");

        if (!data.data || data.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">Không có transaction</td></tr>';
            return;
        }

        tbody.innerHTML = data.data.map(tx => `
            <tr>
                <td>${tx.id}</td>
                <td><strong>${tx.transaction_id}</strong></td>
                <td>${tx.account_id}</td>
                <td>${tx.operation}</td>
                <td class="money">${formatMoney(tx.amount)}</td>
                <td>${statusBadge(tx.status)}</td>
                <td>${new Date(tx.created_at).toLocaleString("vi-VN")}</td>
            </tr>
        `).join("");
    } catch (e) {
        document.getElementById("transactionsBody").innerHTML =
            `<tr><td colspan="7" class="loading" style="color:var(--danger)">Lỗi: ${e.message}</td></tr>`;
    }
}

// =============================================
// Health Check
// =============================================

async function checkHealth() {
    const statusEl = document.getElementById("serverStatus");
    try {
        const data = await apiCall("http://localhost:8001/health");
        const dot = statusEl.querySelector(".status-dot");
        const text = statusEl.querySelector(".status-text");
        if (data.status === "healthy") {
            dot.className = "status-dot online";
            text.textContent = "Bank 1 Online";
        } else {
            dot.className = "status-dot offline";
            text.textContent = "DB Disconnected";
        }
    } catch {
        const dot = statusEl.querySelector(".status-dot");
        const text = statusEl.querySelector(".status-text");
        dot.className = "status-dot offline";
        text.textContent = "Server Offline";
    }
}

// =============================================
// BANK 1 OPERATIONS (Real - với Backend)
// =============================================

async function prepareBank1() {
    const txId = document.getElementById("txId").value.trim();
    const accId = document.getElementById("bank1Account").value;
    const amount = parseFloat(document.getElementById("amount").value);
    const selectedVote = document.getElementById("bank1VoteSelect").value;

    if (!txId) return showToast("Vui lòng nhập Transaction ID", "warning");
    if (!accId) return showToast("Vui lòng chọn tài khoản Bank 1", "warning");
    if (!amount || amount <= 0) return showToast("Vui lòng nhập số tiền hợp lệ", "warning");

    addBankLog('bank1', `Coordinator → PREPARE request`, 'info');
    addFlowStep("prepare", "PREPARE Request", `Bank 1 (${accId}) - Amount: ${formatMoney(amount)}`, "Coordinator");

    // Nếu chọn vote NO - giả lập từ chối
    if (selectedVote === 'NO') {
        txState.bank1.vote = 'NO';
        txState.bank1.status = 'IDLE';
        updateAllUI();

        addBankLog('bank1', `Vote: NO (từ chối prepare)`, 'error');
        addFlowStep("error", "Vote: NO", "Bank 1 từ chối - không đủ điều kiện", "Bank 1");
        showToast("Bank 1: Vote NO", "warning");

        checkAutoRecovery();
        return;
    }

    // Vote YES - gọi API thật
    try {
        const result = await apiCall(`${API_BASE}/prepare`, "POST", {
            transaction_id: txId,
            account_id: accId,
            operation: "DEBIT",
            amount: amount,
        });

        txState.bank1.vote = result.vote;
        txState.bank1.status = 'PREPARED';
        txState.bank1.prepared = true;
        updateAllUI();

        addBankLog('bank1', `Vote: ${result.vote} - Account locked`, 'success');
        addFlowStep("commit", `Vote: ${result.vote}`, `Bank 1 - Account ${accId} locked & prepared`, "Bank 1");
        showToast(`Bank 1 PREPARE: ${result.vote}`, "success");

        loadAccounts();
        loadTransactions();
        checkAutoRecovery();

    } catch (e) {
        txState.bank1.vote = 'NO';
        txState.bank1.status = 'IDLE';
        updateAllUI();

        addBankLog('bank1', `PREPARE failed: ${e.message}`, 'error');
        addFlowStep("error", "PREPARE Failed → Vote NO", e.message, "Bank 1");
        showToast(`Bank 1 PREPARE failed: ${e.message}`, "error");

        loadAccounts();
        loadTransactions();
        checkAutoRecovery();
    }
}

async function commitBank1() {
    const txId = document.getElementById("txId").value.trim();
    if (!txId) return showToast("Vui lòng nhập Transaction ID", "warning");

    addBankLog('bank1', `Coordinator → COMMIT request`, 'info');
    addFlowStep("commit", "COMMIT Request", "Bank 1", "Coordinator");

    try {
        const result = await apiCall(`${API_BASE}/commit`, "POST", {
            transaction_id: txId,
        });

        txState.bank1.status = 'COMMITTED';
        updateAllUI();

        addBankLog('bank1', `COMMITTED - New balance: ${formatMoney(result.new_balance)}`, 'success');
        addFlowStep("commit", "COMMITTED", `Bank 1 - New balance: ${formatMoney(result.new_balance)}`, "Bank 1");
        showToast("Bank 1 COMMIT success", "success");

        loadAccounts();
        loadTransactions();

    } catch (e) {
        addBankLog('bank1', `COMMIT failed: ${e.message}`, 'error');
        addFlowStep("error", "COMMIT Failed", e.message, "Bank 1");
        showToast(`Bank 1 COMMIT failed: ${e.message}`, "error");
        loadAccounts();
        loadTransactions();
    }
}

async function rollbackBank1() {
    const txId = document.getElementById("txId").value.trim();
    if (!txId) return showToast("Vui lòng nhập Transaction ID", "warning");

    addBankLog('bank1', `Coordinator → ROLLBACK request`, 'info');
    addFlowStep("rollback", "ROLLBACK Request", "Bank 1", "Coordinator");

    try {
        await apiCall(`${API_BASE}/rollback`, "POST", {
            transaction_id: txId,
        });

        txState.bank1.status = 'ABORTED';
        updateAllUI();

        addBankLog('bank1', `ROLLED BACK - Account unlocked`, 'warning');
        addFlowStep("rollback", "ROLLED BACK", "Bank 1 - Account unlocked", "Bank 1");
        showToast("Bank 1 ROLLBACK success", "success");

        loadAccounts();
        loadTransactions();

    } catch (e) {
        addBankLog('bank1', `ROLLBACK failed: ${e.message}`, 'error');
        addFlowStep("error", "ROLLBACK Failed", e.message, "Bank 1");
        showToast(`Bank 1 ROLLBACK failed: ${e.message}`, "error");
        loadAccounts();
        loadTransactions();
    }
}

// =============================================
// BANK 2 OPERATIONS (Simulated - Frontend Only)
// =============================================

async function prepareBank2() {
    const txId = document.getElementById("txId").value.trim();
    const accId = document.getElementById("bank2Account").value || 'SIM-ACC-001';
    const amount = parseFloat(document.getElementById("amount").value);
    const selectedVote = document.getElementById("bank2VoteSelect").value;
    const simulateDelay = document.getElementById("bank2SimulateDelay")?.checked;
    const simulateCrash = document.getElementById("bank2SimulateCrash")?.checked;

    if (!txId) return showToast("Vui lòng nhập Transaction ID", "warning");
    if (!amount || amount <= 0) return showToast("Vui lòng nhập số tiền hợp lệ", "warning");

    addBankLog('bank2', `Coordinator → PREPARE request`, 'info');
    addFlowStep("prepare", "PREPARE Request", `Bank 2 (${accId}) - Amount: ${formatMoney(amount)}`, "Coordinator");

    // Simulate delay
    if (simulateDelay) {
        addBankLog('bank2', `⏱️ Network delay (2s)...`, 'info');
        addFlowStep("info", "Simulating delay", "Bank 2 - 2 second network latency", "Bank 2");
        await sleep(2000);
    }

    // Simulate crash after prepare
    if (simulateCrash) {
        txState.crashed = true;
        txState.bank2.status = 'PREPARED'; // Prepared but crashed
        txState.bank2.vote = null; // Vote lost in crash
        updateAllUI();

        addBankLog('bank2', `💥 CRASHED after receiving prepare!`, 'error');
        addFlowStep("crash", "BANK CRASHED", "Bank 2 crashed - no vote response!", "Bank 2");
        showToast("Bank 2 CRASHED!", "error");

        // Coordinator will timeout and abort
        addFlowStep("info", "Coordinator timeout", "No response from Bank 2 → Will ABORT", "Coordinator");
        checkAutoRecovery();
        return;
    }

    // Vote NO
    if (selectedVote === 'NO') {
        txState.bank2.vote = 'NO';
        txState.bank2.status = 'IDLE';
        updateAllUI();

        addBankLog('bank2', `Vote: NO (từ chối - insufficient funds/policy)`, 'error');
        addFlowStep("error", "Vote: NO", "Bank 2 từ chối prepare", "Bank 2");
        showToast("Bank 2: Vote NO", "warning");

        checkAutoRecovery();
        return;
    }

    // Vote YES - simulate success
    txState.bank2.vote = 'YES';
    txState.bank2.status = 'PREPARED';
    txState.bank2.prepared = true;
    txState.bank2.simulatedLocked = true;
    updateAllUI();

    addBankLog('bank2', `Vote: YES - Account locked (simulated)`, 'success');
    addFlowStep("commit", "Vote: YES", `Bank 2 - Account ${accId} locked & prepared (simulated)`, "Bank 2");
    showToast("Bank 2 PREPARE: YES", "success");

    checkAutoRecovery();
}

async function commitBank2() {
    const accId = document.getElementById("bank2Account").value || 'SIM-ACC-001';
    const amount = parseFloat(document.getElementById("amount").value) || 0;
    const simulateCommitFail = document.getElementById("bank2SimulateCommitFail")?.checked;

    addBankLog('bank2', `Coordinator → COMMIT request`, 'info');
    addFlowStep("commit", "COMMIT Request", "Bank 2", "Coordinator");

    // Simulate commit failure
    if (simulateCommitFail) {
        addBankLog('bank2', `💥 COMMIT FAILED - Network error!`, 'error');
        addFlowStep("error", "COMMIT Failed", "Bank 2 - Network error during commit!", "Bank 2");
        showToast("Bank 2 COMMIT failed!", "error");

        addFlowStep("info", "⚠️ Inconsistent State!", "Bank 1 committed but Bank 2 failed - Manual recovery needed", "Coordinator");
        return;
    }

    // Simulate successful commit
    txState.bank2.status = 'COMMITTED';
    txState.bank2.simulatedBalance += amount;
    txState.bank2.simulatedLocked = false;
    updateAllUI();

    addBankLog('bank2', `COMMITTED - Balance: ${formatMoney(txState.bank2.simulatedBalance)} (simulated)`, 'success');
    addFlowStep("commit", "COMMITTED", `Bank 2 - Balance updated (simulated)`, "Bank 2");
    showToast("Bank 2 COMMIT success", "success");
}

async function rollbackBank2() {
    addBankLog('bank2', `Coordinator → ROLLBACK request`, 'info');
    addFlowStep("rollback", "ROLLBACK Request", "Bank 2", "Coordinator");

    if (txState.crashed) {
        addBankLog('bank2', `⚠️ Bank is crashed - rollback may be lost`, 'warning');
        addFlowStep("error", "Cannot Rollback", "Bank 2 is crashed!", "Bank 2");
        showToast("Bank 2 crashed - cannot rollback", "error");
        return;
    }

    // Simulate rollback
    txState.bank2.status = 'ABORTED';
    txState.bank2.simulatedLocked = false;
    updateAllUI();

    addBankLog('bank2', `ROLLED BACK - Account unlocked (simulated)`, 'warning');
    addFlowStep("rollback", "ROLLED BACK", "Bank 2 - Account unlocked (simulated)", "Bank 2");
    showToast("Bank 2 ROLLBACK success", "success");
}

// =============================================
// Coordinator Functions
// =============================================

async function checkAutoRecovery() {
    const autoEnabled = document.getElementById('autoRecoveryEnabled')?.checked;

    // Both voted or crashed
    if (txState.bank1.vote === null && !txState.crashed) return;
    if (txState.bank2.vote === null && !txState.crashed) return;

    updateCoordinatorUI();

    if (!autoEnabled) {
        addFlowStep("coordinator", "Auto-recovery disabled", "Manual decision required", "Coordinator");
        return;
    }

    await sleep(500);

    if (txState.decision === 'COMMIT') {
        addFlowStep("coordinator", "Decision: COMMIT", "All banks voted YES → Auto committing...", "Coordinator");
        await executeCommitAll();
    } else if (txState.decision === 'ABORT') {
        addFlowStep("coordinator", "Decision: ABORT", "Has NO vote or crash → Auto rolling back...", "Coordinator");
        await executeRollbackAll();
    }
}

async function autoDecideAndExecute() {
    if (txState.bank1.vote === null && !txState.crashed) {
        showToast("Bank 1 chưa vote!", "warning");
        return;
    }
    if (txState.bank2.vote === null && !txState.crashed) {
        showToast("Bank 2 chưa vote!", "warning");
        return;
    }

    updateCoordinatorUI();

    if (txState.decision === 'COMMIT') {
        addFlowStep("coordinator", "Decision: COMMIT", "All YES → Executing COMMIT on all banks", "Coordinator");
        await executeCommitAll();
    } else {
        addFlowStep("coordinator", "Decision: ABORT", "Has NO → Executing ROLLBACK on all banks", "Coordinator");
        await executeRollbackAll();
    }
}

async function executeCommitAll() {
    // Commit Bank 1 first
    if (txState.bank1.status === 'PREPARED') {
        await commitBank1();
    }

    // Then Bank 2
    if (txState.bank2.status === 'PREPARED' && !txState.crashed) {
        await commitBank2();
    }

    if (txState.bank1.status === 'COMMITTED' && txState.bank2.status === 'COMMITTED') {
        addFlowStep("info", "🎉 Transaction Complete!", "Both banks committed successfully", "Coordinator");
        showToast("Transaction committed successfully!", "success");
    }
}

async function executeRollbackAll() {
    // Rollback Bank 1 if prepared
    if (txState.bank1.status === 'PREPARED') {
        await rollbackBank1();
    }

    // Rollback Bank 2 if prepared and not crashed
    if (txState.bank2.status === 'PREPARED' && !txState.crashed) {
        await rollbackBank2();
    }

    addFlowStep("info", "Transaction Aborted", "Rollback completed", "Coordinator");
    showToast("Transaction rolled back", "warning");
}

// =============================================
// Full 2PC Auto Execute
// =============================================

async function executeFullTransfer() {
    const txId = document.getElementById("txId").value.trim();
    const bank1Acc = document.getElementById("bank1Account").value;
    const bank2Acc = document.getElementById("bank2Account").value || 'SIM-ACC-001';
    const amount = parseFloat(document.getElementById("amount").value);

    if (!txId) return showToast("Vui lòng nhập Transaction ID", "warning");
    if (!bank1Acc) return showToast("Vui lòng chọn tài khoản Bank 1", "warning");
    if (!amount || amount <= 0) return showToast("Vui lòng nhập số tiền hợp lệ", "warning");

    // Reset first
    resetTransaction();
    document.getElementById("txId").value = txId; // Keep tx ID
    document.getElementById("bank1Account").value = bank1Acc;
    document.getElementById("bank2Account").value = bank2Acc;
    document.getElementById("amount").value = amount;
    await sleep(300);

    addFlowStep("coordinator", "Starting 2PC", `TX: ${txId}, Amount: ${formatMoney(amount)}`, "Coordinator");

    // Phase 1: PREPARE both banks
    addFlowStep("info", "=== PHASE 1: PREPARE ===", "Sending prepare to all participants", "Coordinator");

    // Set votes to YES for auto execution
    document.getElementById("bank1VoteSelect").value = 'YES';
    document.getElementById("bank2VoteSelect").value = 'YES';

    await prepareBank1();
    await sleep(500);
    await prepareBank2();

    // Check decision and execute phase 2
    await sleep(500);

    if (txState.decision) {
        addFlowStep("info", "=== PHASE 2: DECISION ===", `Decision: ${txState.decision}`, "Coordinator");
    }
}

// =============================================
// Quick Test Scenarios
// =============================================

async function runScenario(scenario) {
    const txId = document.getElementById("txId").value.trim();
    const bank1Acc = document.getElementById("bank1Account").value;
    const amount = parseFloat(document.getElementById("amount").value);

    if (!txId) return showToast("Vui lòng nhập Transaction ID", "warning");
    if (!bank1Acc) return showToast("Vui lòng chọn tài khoản Bank 1", "warning");
    if (!amount || amount <= 0) return showToast("Vui lòng nhập số tiền hợp lệ", "warning");

    // Reset and disable auto-recovery for manual control
    resetTransaction();
    const autoRecovery = document.getElementById('autoRecoveryEnabled');
    const wasAutoEnabled = autoRecovery?.checked;
    if (autoRecovery) autoRecovery.checked = false;

    document.getElementById("txId").value = txId;
    document.getElementById("bank1Account").value = bank1Acc;
    document.getElementById("amount").value = amount;
    await sleep(300);

    switch (scenario) {
        case 'happy-path':
            addFlowStep("info", "🧪 Scenario: Happy Path", "Both banks vote YES → COMMIT", "Test");
            document.getElementById("bank1VoteSelect").value = 'YES';
            document.getElementById("bank2VoteSelect").value = 'YES';
            await prepareBank1();
            await sleep(500);
            await prepareBank2();
            await sleep(500);
            addFlowStep("info", "✅ Result", "Both prepared with YES. Click 'Auto Decision' to commit.", "Test");
            break;

        case 'bank1-reject':
            addFlowStep("info", "🧪 Scenario: Bank 1 Rejects", "Bank 1 votes NO → ABORT immediately", "Test");
            document.getElementById("bank1VoteSelect").value = 'NO';
            document.getElementById("bank2VoteSelect").value = 'YES';
            await prepareBank1();
            await sleep(500);
            addFlowStep("info", "❌ Result", "Bank 1 rejected. No need to contact Bank 2.", "Test");
            break;

        case 'bank2-reject':
            addFlowStep("info", "🧪 Scenario: Bank 2 Rejects", "Bank 1 YES, Bank 2 NO → Need rollback Bank 1", "Test");
            document.getElementById("bank1VoteSelect").value = 'YES';
            document.getElementById("bank2VoteSelect").value = 'NO';
            await prepareBank1();
            await sleep(500);
            await prepareBank2();
            await sleep(500);
            addFlowStep("info", "❌ Result", "Bank 2 rejected. Bank 1 is PREPARED and needs ROLLBACK!", "Test");
            break;

        case 'bank2-crash':
            addFlowStep("info", "🧪 Scenario: Bank 2 Crash", "Bank 2 crashes after receiving prepare", "Test");
            document.getElementById("bank1VoteSelect").value = 'YES';
            document.getElementById("bank2SimulateCrash").checked = true;
            await prepareBank1();
            await sleep(500);
            await prepareBank2();
            await sleep(500);
            addFlowStep("info", "💥 Result", "Bank 2 crashed. Coordinator must abort and rollback Bank 1.", "Test");
            break;

        case 'partial-commit':
            addFlowStep("info", "🧪 Scenario: Partial Commit Failure", "Bank 1 commits, Bank 2 fails to commit", "Test");
            document.getElementById("bank1VoteSelect").value = 'YES';
            document.getElementById("bank2VoteSelect").value = 'YES';
            document.getElementById("bank2SimulateCommitFail").checked = true;
            await prepareBank1();
            await sleep(500);
            await prepareBank2();
            await sleep(500);
            // Manual commit to show the issue
            addFlowStep("info", "⚠️ Now commit both banks manually to see the inconsistency", "Bank 2 will fail", "Test");
            break;
    }

    // Restore auto-recovery
    if (autoRecovery) autoRecovery.checked = wasAutoEnabled;
    showToast(`Scenario '${scenario}' loaded`, "info");
}

// =============================================
// Recovery Functions
// =============================================

async function checkRecovery() {
    try {
        const result = await apiCall(`${API_BASE}/recovery/status`);
        const container = document.getElementById("recoveryResult");
        container.style.display = "block";
        container.innerHTML = `
            <div class="recovery-info">
                <h4>Recovery Status</h4>
                <p>Pending transactions: <strong>${result.pending}</strong></p>
                <p>Details: ${JSON.stringify(result.transactions || [])}</p>
            </div>
        `;
        showToast(`Found ${result.pending} pending transactions`, "info");
    } catch (e) {
        showToast(`Recovery check failed: ${e.message}`, "error");
    }
}

async function forceRollbackAll() {
    try {
        const result = await apiCall(`${API_BASE}/recovery/rollback-all`, "POST");
        showToast(`Rolled back ${result.rolled_back || 0} transactions`, "success");
        loadAccounts();
        loadTransactions();
        resetTransaction();
    } catch (e) {
        showToast(`Force rollback failed: ${e.message}`, "error");
    }
}

async function cleanupLocks() {
    try {
        const result = await apiCall(`${API_BASE}/recovery/cleanup-locks`, "POST");
        showToast(`Cleaned up ${result.unlocked || 0} stale locks`, "success");
        loadAccounts();
    } catch (e) {
        showToast(`Cleanup failed: ${e.message}`, "error");
    }
}

// =============================================
// Event Listeners & Init
// =============================================

document.addEventListener("DOMContentLoaded", () => {
    generateTxId();
    checkHealth();
    loadAccounts();
    loadTransactions();
    updateAllUI();

    // Update account displays on change
    document.getElementById("bank1Account")?.addEventListener("change", updateAccountDisplays);
    document.getElementById("bank2Account")?.addEventListener("input", updateAccountDisplays);

    // Auto refresh
    setInterval(checkHealth, 30000);
});
