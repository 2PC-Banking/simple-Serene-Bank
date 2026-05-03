# Bank System - Mô phỏng Participant 2PC

Ứng dụng này mô phỏng một participant bank trong giao thức Two-Phase Commit (2PC). Backend nhận request PREPARE/COMMIT/ROLLBACK từ coordinator và cập nhật trạng thái giao dịch trong SQL Server.

## Tổng quan kiến trúc

Hệ thống gồm:

- Frontend HTML/CSS/JS để test luồng 2PC participant
- Backend FastAPI đóng vai participant bank
- SQL Server lưu account và transaction log

Luồng xử lý participant:

1. Phase 1: nhận PREPARE, kiểm tra điều kiện, lock account, trả vote YES/NO
2. Phase 2: nhận decision COMMIT hoặc ROLLBACK từ coordinator, apply vào DB, trả ACK

## Chạy nhanh với Docker

```bash
docker compose up -d --build
```

Truy cập:

- Frontend: <http://localhost:8080>
- Backend API: <http://localhost:8001>
- Swagger: <http://localhost:8001/docs>

Dừng hệ thống:

```bash
docker compose down
```

## Chạy local

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m app.main
```

### Frontend

Mở frontend/index.html hoặc chạy qua nginx/docker.

## Khả năng nhận request từ coordinator

Participant backend đã sẵn sàng nhận call từ coordinator theo 2 kiểu:

1. Server-to-server (coordinator backend gọi thẳng participant): không bị ảnh hưởng bởi browser CORS.
2. Browser-based coordinator UI (JS call trực tiếp participant): cần CORS hợp lệ.

### CORS đã được harden

Backend sử dụng biến môi trường để cấu hình CORS:

- CORS_ALLOW_ORIGINS (mặc định: *)
- CORS_ALLOW_METHODS (mặc định: *)
- CORS_ALLOW_HEADERS (mặc định: *)
- CORS_ALLOW_CREDENTIALS (mặc định: false)

Lưu ý quan trọng:

- Nếu CORS_ALLOW_ORIGINS=* thì không được dùng credentials=true theo CORS spec của browser.
- App tự động force credentials=false trong trường hợp wildcard origin để tránh lỗi CORS.
- Nếu coordinator cần gửi cookie/session, hãy đặt CORS_ALLOW_ORIGINS thành danh sách origin cụ thể và bật CORS_ALLOW_CREDENTIALS=true.

Ví dụ .env cho coordinator web app:

```env
CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:8080
CORS_ALLOW_METHODS=GET,POST,OPTIONS
CORS_ALLOW_HEADERS=Content-Type,Authorization
CORS_ALLOW_CREDENTIALS=true
```

## API chi tiết phía Bank Participant

Các endpoint participant hiện có trong project này:

| Method | Endpoint | Mục đích |
| --- | --- | --- |
| POST | /api/prepare | Phase 1: participant vote YES/NO |
| POST | /api/prepare/coordinator-payload | Trả payload mẫu để coordinator gọi PREPARE |
| POST | /api/commit | Phase 2: apply commit |
| POST | /api/rollback | Phase 2: apply rollback |
| GET | /api/recovery/status | Kiểm tra transaction PREPARED đang pending |
| POST | /api/recovery/force-rollback | Force rollback tất cả PREPARED |
| POST | /api/recovery/auto-rollback-expired | Rollback các PREPARED quá timeout |
| POST | /api/recovery/cleanup-locks | Dọn lock stale |

### 1) POST /api/prepare

Request:

```json
{
  "transaction_id": "TX-2026-0001-DEBIT",
  "account_id": "ACC001",
  "operation": "DEBIT",
  "amount": 100000,
  "simulate_delay_ms": 0,
  "simulate_crash_before_vote": false
}
```

Response 200 (vote YES):

```json
{
  "transaction_id": "TX-2026-0001-DEBIT",
  "vote": "YES",
  "message": "Prepare successful. Account 'ACC001' locked and ready.",
  "account_id": "ACC001",
  "operation": "DEBIT",
  "amount": 100000.0
}
```

Response lỗi thường gặp:

- 400: không đủ số dư (DEBIT)
- 404: không tìm thấy account
- 409: account đang bị lock bởi transaction khác
- 500: lỗi nội bộ hoặc mô phỏng crash trước vote

### 2) POST /api/commit

Request:

```json
{
  "transaction_id": "TX-2026-0001-DEBIT",
  "simulate_delay_ms": 0,
  "simulate_fail_before_apply": false,
  "simulate_crash": false
}
```

Response 200:

```json
{
  "transaction_id": "TX-2026-0001-DEBIT",
  "status": "COMMITTED",
  "message": "Transaction committed. DEBIT 100,000.00 on account 'ACC001'.",
  "account_id": "ACC001",
  "operation": "DEBIT",
  "amount": 100000.0,
  "new_balance": 9900000.0
}
```
****
Response lỗi thường gặp:

- 404: không tìm thấy transaction_id
- 500: simulate_fail_before_apply hoặc simulate_crash

### 3) POST /api/rollback

Request:

```json
{
  "transaction_id": "TX-2026-0001-DEBIT",
  "simulate_delay_ms": 0,
  "simulate_crash_before_apply": false,
  "simulate_crash_after_apply": false
}
```

Response 200:

```json
{
  "transaction_id": "TX-2026-0001-DEBIT",
  "status": "ABORTED",
  "message": "Transaction rolled back. Account 'ACC001' unlocked.",
  "account_id": "ACC001"
}
```

Response lỗi thường gặp:

- 404: không tìm thấy transaction_id
- 500: crash trước apply hoặc crash sau apply (ACK bị mất)

### 4) GET /api/recovery/status

Response 200:

```json
{
  "status": "success",
  "recovered": 0,
  "pending": 1,
  "details": [
    {
      "transaction_id": "TX-2026-0001-DEBIT",
      "account_id": "ACC001",
      "operation": "DEBIT",
      "amount": 100000.0,
      "status": "PREPARED",
      "created_at": "2026-03-28T10:00:00"
    }
  ]
}
```

## API chi tiết phía Coordinator Server (đề xuất chuẩn tích hợp)

Lưu ý: repository hiện tại tập trung participant bank. Phần dưới đây là contract đề xuất để bạn triển khai coordinator riêng và đồng bộ với participant API phía trên.

### 1) POST /coordinator/transfers

Mục đích: nhận yêu cầu chuyển tiền từ client, tạo global transaction_id và chạy luồng 2PC.

Request:

```json
{
  "client_tx_id": "CLI-2026-0001",
  "from_account": "ACC001",
  "to_account": "ACC002",
  "amount": 100000,
  "currency": "VND",
  "participants": [
    {
      "name": "bank-source",
      "base_url": "http://bank-source:8001",
      "account_id": "ACC001",
      "operation": "DEBIT"
    },
    {
      "name": "bank-dest",
      "base_url": "http://bank-dest:8001",
      "account_id": "ACC002",
      "operation": "CREDIT"
    }
  ],
  "timeout_ms": 3000
}
```

Response 202:

```json
{
  "transaction_id": "TX-2026-0001",
  "status": "PROCESSING",
  "phase": "PREPARE",
  "message": "Coordinator accepted transfer request and started 2PC"
}
```

### 2) GET /coordinator/transfers/{transaction_id}

Mục đích: truy vấn trạng thái 2PC hiện tại và kết quả cuối cùng.

Response 200:

```json
{
  "transaction_id": "TX-2026-0001",
  "client_tx_id": "CLI-2026-0001",
  "status": "COMMITTED",
  "phase": "DONE",
  "decision": "COMMIT",
  "participants": [
    {
      "name": "bank-source",
      "prepare_vote": "YES",
      "decision_ack": "ACK"
    },
    {
      "name": "bank-dest",
      "prepare_vote": "YES",
      "decision_ack": "ACK"
    }
  ],
  "created_at": "2026-03-28T10:00:00",
  "updated_at": "2026-03-28T10:00:02"
}
```

### 3) POST /coordinator/transfers/{transaction_id}/retry-decision

Mục đích: retry broadcast COMMIT/ROLLBACK khi mất ACK ở phase 2.

Request:

```json
{
  "max_retry": 3,
  "retry_interval_ms": 500
}
```

Response 200:

```json
{
  "transaction_id": "TX-2026-0001",
  "status": "COMMITTED",
  "decision": "COMMIT",
  "retried": true,
  "remaining_unacked": []
}
```

## Luồng coordinator và participant (2 phase)

### 1) Coordinator nhận request chuyển tiền

1. Người dùng gửi lệnh chuyển tiền đến coordinator.
2. Coordinator tạo global transaction_id (ví dụ TX-2026-0001).
3. Coordinator xác định danh sách participant cần tham gia (nguồn, đích, fee service nếu có).

### 2) Phase 1 - PREPARE

1. Coordinator gửi POST /api/prepare đến từng participant.
2. Mỗi participant kiểm tra:
   - account tồn tại
   - account chưa bị lock bởi transaction khác
   - nếu DEBIT thì số dư đủ
3. Nếu hợp lệ, participant:
   - lock account
   - ghi transaction status PREPARED
   - trả vote=YES
4. Nếu thất bại hoặc timeout/crash trước vote, coordinator xem như vote NO/UNKNOWN.

### 3) Phase 2 - DECISION

Nếu tất cả vote YES:

1. Coordinator broadcast POST /api/commit.
2. Participant apply thay đổi số dư, cập nhật COMMITTED, unlock account, trả ACK.
3. Trường hợp crash sau khi DB đã commit (simulate_crash): coordinator có thể không nhận được ACK, cần retry hoặc recovery theo transaction log.

Nếu có bất kỳ vote NO/timeout:

1. Coordinator broadcast POST /api/rollback.
2. Participant cập nhật ABORTED, unlock account, không đổi số dư, trả ACK.
3. Nếu ACK bị mất sau khi rollback apply, coordinator cần retry idempotent đến khi đạt trạng thái cuối cùng.

### 4) Recovery

1. Khi participant khởi động lại, hệ thống tự check các transaction PREPARED.
2. Có thể dùng API recovery để force rollback, auto-rollback quá timeout, và cleanup lock stale.
3. Coordinator nên có cơ chế retry decision và đối chiếu trạng thái theo transaction_id.

## Mapping trạng thái giữa coordinator và participant

| Coordinator status | Participant status điển hình |
| --- | --- |
| PROCESSING_PREPARE | PREPARED hoặc chưa có log do timeout |
| PROCESSING_DECISION | COMMITTED hoặc ABORTED tùy decision |
| COMMITTED | Tất cả participant COMMITTED (hoặc đã idempotent commit) |
| ABORTED | Participant ABORTED hoặc rollback hoàn tất |
| IN_DOUBT | Có participant chưa ACK phase 2, cần retry/recovery |

## Các flag mô phỏng lỗi hỗ trợ hiện tại

Phase 1 (/api/prepare):

- simulate_delay_ms
- simulate_crash_before_vote

Phase 2 COMMIT (/api/commit):

- simulate_delay_ms
- simulate_fail_before_apply
- simulate_crash

Phase 2 ROLLBACK (/api/rollback):

- simulate_delay_ms
- simulate_crash_before_apply
- simulate_crash_after_apply

## Thư mục chính****

```text
backend/
  app/
    api/
    core/
    models/
    schemas/
    services/
frontend/
  index.html
  css/style.css
  js/main.js
database/
  schema.sql
  seed.sql
docs/
  api_contract.md
```

## Ghi chú

- Chi tiết request/response đầy đủ xem trong docs/api_contract.md
- Hệ thống đang focus vào participant side. Nếu bạn xây coordinator riêng, hãy giữ nguyên transaction_id và retry idempotent ở phase 2.
