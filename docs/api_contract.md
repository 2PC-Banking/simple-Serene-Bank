# API Contract — Bank System 2PC

## Base URL

```
http://localhost:8001
```

---

## 1. Health Check

### `GET /health`

**Response 200:**
```json
{
    "status": "healthy",
    "database": "connected",
    "service": "Bank-2PC"
}
```

---

## 2. Accounts

### `GET /api/accounts`

Lấy danh sách tất cả tài khoản.

**Response 200:**
```json
{
    "status": "success",
    "count": 5,
    "data": [
        {
            "account_id": "ACC001",
            "account_name": "Nguyễn Văn A",
            "balance": 10000000.0,
            "is_locked": false,
            "locked_by_tx": null,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00"
        }
    ]
}
```

### `GET /api/accounts/{account_id}`

Lấy thông tin một tài khoản.

**Response 200:**
```json
{
    "status": "success",
    "data": { ... }
}
```

**Response 404:**
```json
{
    "detail": "Account 'ACC999' not found"
}
```

### `GET /api/accounts/{account_id}/balance`

Lấy số dư tài khoản.

**Response 200:**
```json
{
    "status": "success",
    "account_id": "ACC001",
    "account_name": "Nguyễn Văn A",
    "balance": 10000000.0,
    "is_locked": false,
    "locked_by_tx": null
}
```

---

## 3. Transactions

### `GET /api/transactions`

Lấy danh sách transaction log. Hỗ trợ filter.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `status_filter` | string | Filter theo status: INIT, PREPARED, COMMITTED, ABORTED |
| `account_id` | string | Filter theo account ID |

**Response 200:**
```json
{
    "status": "success",
    "count": 2,
    "data": [
        {
            "id": 1,
            "transaction_id": "TX-001-DEBIT",
            "account_id": "ACC001",
            "operation": "DEBIT",
            "amount": 100000.0,
            "status": "COMMITTED",
            "created_at": "2024-01-01T10:00:00",
            "updated_at": "2024-01-01T10:00:05"
        }
    ]
}
```

### `GET /api/transactions/{transaction_id}`

Lấy chi tiết transaction theo transaction_id.

---

## 4. Two-Phase Commit

### `POST /api/prepare` — Phase 1

**Request Body:**
```json
{
    "transaction_id": "TX-2024-001-DEBIT",
    "account_id": "ACC001",
    "operation": "DEBIT",
    "amount": 100000.00
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `transaction_id` | string | ✅ | Global TX ID từ Coordinator |
| `account_id` | string | ✅ | ID tài khoản |
| `operation` | string | ✅ | `DEBIT` hoặc `CREDIT` |
| `amount` | number | ✅ | Số tiền (> 0) |

**Response 200 (Vote YES):**
```json
{
    "transaction_id": "TX-2024-001-DEBIT",
    "vote": "YES",
    "message": "Prepare successful. Account 'ACC001' locked and ready.",
    "account_id": "ACC001",
    "operation": "DEBIT",
    "amount": 100000.0
}
```

**Response 404 (Account not found):**
```json
{
    "detail": "Account 'ACC999' not found"
}
```

**Response 409 (Account locked):**
```json
{
    "detail": "Account 'ACC001' is locked by transaction 'TX-OTHER'"
}
```

**Response 400 (Insufficient balance):**
```json
{
    "detail": "Insufficient balance for account 'ACC001': balance=5000.0, required=10000.0"
}
```

---

### `POST /api/commit` — Phase 2

**Request Body:**
```json
{
    "transaction_id": "TX-2024-001-DEBIT"
}
```

**Response 200:**
```json
{
    "transaction_id": "TX-2024-001-DEBIT",
    "status": "COMMITTED",
    "message": "Transaction committed. DEBIT 100,000.00 on account 'ACC001'.",
    "account_id": "ACC001",
    "operation": "DEBIT",
    "amount": 100000.0,
    "new_balance": 9900000.0
}
```

**Response 404:**
```json
{
    "detail": "Transaction 'TX-999' not found"
}
```

---

### `POST /api/rollback` — Phase 2 (Alternative)

**Request Body:**
```json
{
    "transaction_id": "TX-2024-001-DEBIT"
}
```

**Response 200:**
```json
{
    "transaction_id": "TX-2024-001-DEBIT",
    "status": "ABORTED",
    "message": "Transaction rolled back. Account 'ACC001' unlocked.",
    "account_id": "ACC001"
}
```

---

## 5. Recovery

### `GET /api/recovery/status`

Kiểm tra các transaction đang pending (PREPARED).

**Response 200:**
```json
{
    "status": "success",
    "recovered": 0,
    "pending": 1,
    "details": [
        {
            "transaction_id": "TX-001-DEBIT",
            "account_id": "ACC001",
            "operation": "DEBIT",
            "amount": 100000.0,
            "status": "PREPARED",
            "created_at": "2024-01-01T10:00:00"
        }
    ]
}
```

### `POST /api/recovery/force-rollback`

Force rollback tất cả transaction PREPARED.

**Response 200:**
```json
{
    "status": "success",
    "rolled_back_count": 2,
    "transaction_ids": ["TX-001-DEBIT", "TX-001-CREDIT"]
}
```

### `POST /api/recovery/cleanup-locks`

Dọn dẹp các lock cũ không còn transaction tương ứng.

**Response 200:**
```json
{
    "status": "success",
    "cleaned_count": 1,
    "details": [
        {
            "account_id": "ACC001",
            "was_locked_by": "TX-OLD"
        }
    ]
}
```
