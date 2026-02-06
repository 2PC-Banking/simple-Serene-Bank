-- =============================================
-- Database Schema for Bank System (2PC - Two Phase Commit)
-- SQL Server
-- =============================================

-- Tạo database (nếu chưa có)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'BankDB')
BEGIN
    CREATE DATABASE BankDB;
END
GO

USE BankDB;
GO

-- =============================================
-- Bảng ACCOUNTS: Lưu thông tin tài khoản
-- =============================================
IF OBJECT_ID('dbo.accounts', 'U') IS NOT NULL
    DROP TABLE dbo.accounts;
GO

CREATE TABLE dbo.accounts (
    account_id      VARCHAR(50)     PRIMARY KEY,
    account_name    NVARCHAR(100)   NOT NULL,
    balance         DECIMAL(18, 2)  NOT NULL DEFAULT 0.00,
    is_locked       BIT             NOT NULL DEFAULT 0,          -- 1 = đang bị khóa bởi transaction
    locked_by_tx    VARCHAR(100)    NULL,                        -- Transaction ID đang khóa
    created_at      DATETIME        NOT NULL DEFAULT GETDATE(),
    updated_at      DATETIME        NOT NULL DEFAULT GETDATE(),
    
    CONSTRAINT CHK_balance_positive CHECK (balance >= 0)
);
GO

-- =============================================
-- Bảng TRANSACTION_LOG: Lưu trạng thái giao dịch 2PC
-- =============================================
IF OBJECT_ID('dbo.transaction_log', 'U') IS NOT NULL
    DROP TABLE dbo.transaction_log;
GO

CREATE TABLE dbo.transaction_log (
    id              INT             IDENTITY(1,1) PRIMARY KEY,
    transaction_id  VARCHAR(100)    NOT NULL,                    -- Global Transaction ID từ Coordinator
    account_id      VARCHAR(50)     NOT NULL,
    operation       VARCHAR(20)     NOT NULL,                    -- 'DEBIT' hoặc 'CREDIT'
    amount          DECIMAL(18, 2)  NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'INIT',     -- INIT, PREPARED, COMMITTED, ABORTED
    created_at      DATETIME        NOT NULL DEFAULT GETDATE(),
    updated_at      DATETIME        NOT NULL DEFAULT GETDATE(),
    
    CONSTRAINT FK_transaction_account FOREIGN KEY (account_id) 
        REFERENCES dbo.accounts(account_id),
    CONSTRAINT CHK_operation CHECK (operation IN ('DEBIT', 'CREDIT')),
    CONSTRAINT CHK_status CHECK (status IN ('INIT', 'PREPARED', 'COMMITTED', 'ABORTED')),
    CONSTRAINT CHK_amount_positive CHECK (amount > 0)
);
GO

-- Index để tìm kiếm nhanh theo transaction_id
CREATE INDEX IX_transaction_log_tx_id ON dbo.transaction_log(transaction_id);
GO

-- Index để tìm kiếm các transaction đang PREPARED (dùng cho recovery)
CREATE INDEX IX_transaction_log_status ON dbo.transaction_log(status) WHERE status = 'PREPARED';
GO

-- =============================================
-- Trigger: Tự động cập nhật updated_at
-- =============================================
CREATE OR ALTER TRIGGER trg_accounts_update
ON dbo.accounts
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.accounts
    SET updated_at = GETDATE()
    FROM dbo.accounts a
    INNER JOIN inserted i ON a.account_id = i.account_id;
END
GO

CREATE OR ALTER TRIGGER trg_transaction_log_update
ON dbo.transaction_log
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.transaction_log
    SET updated_at = GETDATE()
    FROM dbo.transaction_log t
    INNER JOIN inserted i ON t.id = i.id;
END
GO

PRINT 'Schema created successfully!';
GO
