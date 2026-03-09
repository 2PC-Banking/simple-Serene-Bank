# Crash Recovery — Test Scenarios

## Giới thiệu

Tài liệu mô tả các kịch bản crash recovery trong hệ thống 2PC Bank System.
Mục đích: kiểm tra tính bền vững (durability) và khả năng phục hồi sau sự cố.

---

## Kịch bản 1: Crash sau PREPARE, trước COMMIT

### Mô tả
- Coordinator gửi PREPARE → nhận vote YES
- **Server crash** trước khi gửi COMMIT

### Trạng thái sau crash
- `transaction_log`: status = `PREPARED`
- `accounts`: `is_locked = 1`, `locked_by_tx = 'TX-xxx'`
- Balance chưa thay đổi

### Recovery
1. Khởi động lại server → `RecoveryService.recover_pending_transactions()` tự động chạy
2. Hệ thống log danh sách TX đang PREPARED
3. Coordinator có thể:
   - Gửi lại `POST /api/commit` → hoàn tất giao dịch
   - Gửi `POST /api/rollback` → hủy giao dịch

### Test steps
```
1. POST /api/prepare  → TX-CRASH-001-DEBIT, ACC001, DEBIT, 100000
2. Verify: GET /api/accounts/ACC001 → is_locked = true
3. Kill server (Ctrl+C)
4. Restart server
5. Check logs: "Found 1 pending transaction(s)"
6. Option A: POST /api/commit   {"transaction_id": "TX-CRASH-001-DEBIT"}
   Option B: POST /api/rollback {"transaction_id": "TX-CRASH-001-DEBIT"}
7. Verify: GET /api/accounts/ACC001 → is_locked = false
```

---

## Kịch bản 2: Crash sau COMMIT một phần

### Mô tả
- Chuyển tiền ACC001 → ACC002
- DEBIT đã COMMITTED
- **Server crash** trước khi CREDIT được COMMITTED

### Trạng thái sau crash
- TX-DEBIT: status = `COMMITTED` ✅
- TX-CREDIT: status = `PREPARED` ⚠️
- ACC001: unlocked, balance đã giảm
- ACC002: locked, balance chưa tăng

### Recovery
1. Restart server
2. Recovery phát hiện TX-CREDIT đang PREPARED
3. Coordinator gửi `POST /api/commit` cho TX-CREDIT
4. ACC002 được cập nhật balance và unlock

### Test steps
```
1. POST /api/prepare  → TX-CRASH-002-DEBIT, ACC001, DEBIT, 50000
2. POST /api/prepare  → TX-CRASH-002-CREDIT, ACC002, CREDIT, 50000
3. POST /api/commit   → TX-CRASH-002-DEBIT  (success)
4. Kill server before committing CREDIT
5. Restart server
6. GET /api/recovery/status → shows TX-CRASH-002-CREDIT as PREPARED
7. POST /api/commit → TX-CRASH-002-CREDIT
8. Verify balances
```

---

## Kịch bản 3: Stale locks

### Mô tả
- Transaction PREPARED nhưng transaction log bị xóa thủ công
- Account vẫn locked nhưng không có TX tương ứng

### Recovery
```
1. POST /api/recovery/cleanup-locks
2. Verify locked accounts → should be 0
```

---

## Kịch bản 4: Force rollback tất cả

### Mô tả
- Nhiều transaction PREPARED bị treo
- Admin quyết định rollback toàn bộ

### Recovery
```
1. POST /api/recovery/force-rollback
2. Verify: tất cả accounts → is_locked = false
3. Verify: tất cả PREPARED → status = ABORTED
```

---

## API Recovery

| Endpoint | Method | Mô tả |
|----------|--------|--------|
| `/api/recovery/status` | GET | Liệt kê TX đang PREPARED |
| `/api/recovery/force-rollback` | POST | Force abort tất cả PREPARED |
| `/api/recovery/cleanup-locks` | POST | Xóa lock mồ côi |

---

## Idempotency

Tất cả API đều idempotent:
- `prepare` lần 2 → trả YES (không tạo log mới)
- `commit` lần 2 → trả COMMITTED (không apply lại)
- `rollback` lần 2 → trả ABORTED

Điều này đảm bảo Coordinator có thể retry an toàn sau crash.
