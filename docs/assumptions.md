# Assumptions & Design Decisions

## 1. Kiến trúc

- **Single Participant**: Hệ thống demo này chỉ có 1 participant (1 database).
  Frontend đóng vai trò Coordinator, gọi prepare → commit/rollback tuần tự.
- **Chuyển tiền = 2 sub-transaction**: Mỗi lệnh chuyển tiền tạo ra 2 transaction con:
  - `{TX_ID}-DEBIT`: Trừ tiền tài khoản nguồn
  - `{TX_ID}-CREDIT`: Cộng tiền tài khoản đích
- Cả 2 phải PREPARE thành công thì mới COMMIT, ngược lại ROLLBACK toàn bộ.

## 2. Database

- Sử dụng **SQL Server** với **Windows Authentication** (Trusted Connection).
- Database `BankDB` sẽ được tự động tạo khi khởi động ứng dụng nếu chưa tồn tại.
- Schema và seed data cũng được tự động khởi tạo.

## 3. Locking

- Mỗi tài khoản chỉ có thể bị khóa bởi **1 transaction** tại một thời điểm.
- Cột `is_locked` và `locked_by_tx` trong bảng `accounts` quản lý trạng thái lock.
- Lock sử dụng **application-level locking** (không dùng database-level lock).
- `SELECT ... FOR UPDATE` (via SQLAlchemy `with_for_update()`) được sử dụng để tránh race condition.

## 4. Idempotency

- Các API `prepare`, `commit`, `rollback` được thiết kế **idempotent**:
  - Gọi `prepare` lần 2 với cùng transaction → trả YES mà không tạo log mới.
  - Gọi `commit` lần 2 → trả kết quả committed mà không apply lại.
  - Gọi `rollback` lần 2 → trả kết quả aborted.
- Điều này quan trọng cho recovery khi Coordinator retry sau crash.

## 5. Transaction Status Flow

```
INIT → PREPARED → COMMITTED
                → ABORTED
```

- **INIT**: Transaction vừa được tạo (không sử dụng trong flow hiện tại)
- **PREPARED**: Lock đã được thiết lập, sẵn sàng commit/rollback
- **COMMITTED**: Balance đã thay đổi, lock đã mở
- **ABORTED**: Transaction bị hủy, lock đã mở, balance không đổi

## 6. Recovery

- Khi hệ thống restart, `RecoveryService` kiểm tra các transaction ở trạng thái `PREPARED`.
- Các transaction PREPARED sẽ chờ Coordinator gửi lệnh tiếp.
- Có thể force rollback tất cả qua API `/api/recovery/force-rollback`.
- Stale locks (lock mồ côi không có TX tương ứng) có thể cleanup qua `/api/recovery/cleanup-locks`.

## 7. Giới hạn

- **Không có timeout tự động**: Transaction PREPARED sẽ giữ lock vô thời hạn cho đến khi được commit/rollback hoặc force-rollback.
- **Không có distributed coordinator**: Frontend đóng vai trò coordinator đơn giản.
- **Không có persistent coordinator log**: Nếu browser crash giữa prepare và commit, cần dùng recovery API.
- **Concurrency**: Tuy có row-level locking (FOR UPDATE), hệ thống chưa xử lý deadlock detection.
- **Balance constraint**: Constraint `CHECK (balance >= 0)` ở database level đảm bảo không trừ âm.

## 8. Công nghệ

| Thành phần | Công nghệ |
|------------|-----------|
| Backend | FastAPI (Python 3.10+) |
| ORM | SQLAlchemy 2.0 |
| Database | SQL Server (ODBC Driver 17) |
| Frontend | Vanilla HTML/CSS/JS |
| Auth | Windows Authentication (Trusted Connection) |
