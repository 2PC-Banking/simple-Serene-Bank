# Bank System — Two-Phase Commit (2PC)

Hệ thống ngân hàng demo triển khai giao thức **Two-Phase Commit** (2PC) để đảm bảo tính nhất quán dữ liệu khi chuyển tiền giữa các tài khoản.

## Kiến trúc

```
┌───────────────┐         ┌───────────────────────┐
│   Frontend    │  HTTP   │   Backend (FastAPI)    │
│   HTML/CSS/JS │ ──────► │   2PC Participant      │
└───────────────┘         │                        │
                          │  /api/prepare           │
                          │  /api/commit            │
                          │  /api/rollback          │
                          │  /api/accounts          │
                          │  /api/transactions      │
                          └──────────┬──────────────┘
                                     │
                                     ▼
                          ┌───────────────────────┐
                          │   SQL Server (BankDB)  │
                          │   - accounts           │
                          │   - transaction_log    │
                          └───────────────────────┘
```

## Yêu cầu

- **Python** 3.10+
- **SQL Server** (LocalDB hoặc full instance)
- **ODBC Driver 17 for SQL Server**

## Cài đặt & Chạy

### 1. Cài đặt dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Cấu hình database

Mặc định sử dụng Windows Authentication kết nối localhost.  
Chỉnh sửa file `backend/app/core/config.py` hoặc tạo file `.env` nếu cần.

### 3. Khởi động Backend

```bash
cd backend
python -m app.main
```

Server sẽ chạy tại: `http://localhost:8001`  
API docs: `http://localhost:8001/docs`

### 4. Mở Frontend

Mở file `frontend/index.html` trực tiếp trong trình duyệt.

## Two-Phase Commit Flow

### Phase 1: PREPARE
1. Coordinator gửi `POST /api/prepare` cho mỗi participant
2. Participant kiểm tra:
   - Tài khoản tồn tại?
   - Tài khoản chưa bị khóa?
   - Số dư đủ? (nếu DEBIT)
3. Nếu OK → Lock account, ghi log `PREPARED`, vote **YES**
4. Nếu FAIL → vote **NO**

### Phase 2: COMMIT hoặc ROLLBACK
- **Tất cả vote YES** → Coordinator gửi `POST /api/commit`
  - Apply balance change (DEBIT/CREDIT)
  - Update status → `COMMITTED`
  - Unlock account
- **Có vote NO** → Coordinator gửi `POST /api/rollback`
  - Update status → `ABORTED`
  - Unlock account
  - Balance không thay đổi

## API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/health` | Health check |
| GET | `/api/accounts` | Danh sách tài khoản |
| GET | `/api/accounts/{id}` | Chi tiết tài khoản |
| GET | `/api/accounts/{id}/balance` | Số dư |
| GET | `/api/transactions` | Transaction logs |
| GET | `/api/transactions/{tx_id}` | Chi tiết transaction |
| POST | `/api/prepare` | Phase 1: Prepare |
| POST | `/api/commit` | Phase 2: Commit |
| POST | `/api/rollback` | Phase 2: Rollback |
| GET | `/api/recovery/status` | Kiểm tra TX pending |
| POST | `/api/recovery/force-rollback` | Force rollback all |
| POST | `/api/recovery/cleanup-locks` | Cleanup stale locks |

## Cấu trúc thư mục

```
BankSystem/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # Entry point
│       ├── api/                  # API endpoints
│       │   ├── balance.py
│       │   ├── prepare.py
│       │   ├── commit.py
│       │   └── rollback.py
│       ├── core/                 # Config & DB
│       │   ├── config.py
│       │   └── database.py
│       ├── models/               # SQLAlchemy models
│       │   ├── account_model.py
│       │   └── transaction_model.py
│       ├── schemas/              # Pydantic schemas
│       │   ├── prepare_schema.py
│       │   ├── commit_schema.py
│       │   └── rollback_schema.py
│       ├── services/             # Business logic
│       │   ├── lock_service.py
│       │   ├── transaction_service.py
│       │   └── recovery_service.py
│       └── utils/
│           ├── exceptions.py
│           └── logger.py
├── database/
│   ├── schema.sql               # DDL
│   ├── seed.sql                 # Sample data
│   └── test_queries.sql         # Test queries
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/main.js
├── docs/
│   ├── api_contract.md
│   └── assumptions.md
└── tests/
    ├── test_prepare.http
    ├── test_commit.http
    ├── test_rollback.http
    └── crash_recovery.md
```
