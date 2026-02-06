-- =============================================
-- Test Queries for 2PC Bank System
-- =============================================
USE BankDB;
GO -- =============================================
    -- 1. TEST: Xem tất cả tài khoản
    -- =============================================
SELECT *
FROM dbo.accounts;
GO -- =============================================
    -- 2. TEST: Xem tất cả transaction log
    -- =============================================
SELECT *
FROM dbo.transaction_log
ORDER BY created_at DESC;
GO -- =============================================
    -- 3. TEST: Kiểm tra tài khoản đang bị khóa
    -- =============================================
SELECT account_id,
    account_name,
    balance,
    locked_by_tx
FROM dbo.accounts
WHERE is_locked = 1;
GO -- =============================================
    -- 4. TEST: Kiểm tra transaction đang ở trạng thái PREPARED
    -- (Dùng cho Recovery khi restart)
    -- =============================================
SELECT transaction_id,
    account_id,
    operation,
    amount,
    status,
    created_at
FROM dbo.transaction_log
WHERE status = 'PREPARED';
GO -- =============================================
    -- 5. TEST: Mô phỏng PREPARE phase (lock account + ghi log)
    -- =============================================
DECLARE @tx_id VARCHAR(100) = 'TX-TEST-001';
DECLARE @acc_id VARCHAR(50) = 'ACC001';
DECLARE @amount DECIMAL(18, 2) = 100000.00;
BEGIN TRANSACTION;
-- Kiểm tra tài khoản có bị khóa không
IF EXISTS (
    SELECT 1
    FROM dbo.accounts
    WHERE account_id = @acc_id
        AND is_locked = 1
) BEGIN PRINT 'Account is locked by another transaction!';
ROLLBACK;
END
ELSE BEGIN -- Kiểm tra số dư đủ không (cho DEBIT)
IF EXISTS (
    SELECT 1
    FROM dbo.accounts
    WHERE account_id = @acc_id
        AND balance >= @amount
) BEGIN -- Lock account
UPDATE dbo.accounts
SET is_locked = 1,
    locked_by_tx = @tx_id
WHERE account_id = @acc_id;
-- Ghi transaction log với status PREPARED
INSERT INTO dbo.transaction_log (
        transaction_id,
        account_id,
        operation,
        amount,
        status
    )
VALUES (@tx_id, @acc_id, 'DEBIT', @amount, 'PREPARED');
COMMIT;
PRINT 'PREPARE successful! Vote: YES';
END
ELSE BEGIN PRINT 'Insufficient balance! Vote: NO';
ROLLBACK;
END
END
GO -- =============================================
    -- 6. TEST: Mô phỏng COMMIT phase
    -- =============================================
DECLARE @tx_id VARCHAR(100) = 'TX-TEST-001';
BEGIN TRANSACTION;
-- Lấy thông tin transaction
DECLARE @acc_id VARCHAR(50),
    @operation VARCHAR(20),
    @amount DECIMAL(18, 2);
SELECT @acc_id = account_id,
    @operation = operation,
    @amount = amount
FROM dbo.transaction_log
WHERE transaction_id = @tx_id
    AND status = 'PREPARED';
IF @acc_id IS NOT NULL BEGIN -- Thực hiện thay đổi balance
IF @operation = 'DEBIT'
UPDATE dbo.accounts
SET balance = balance - @amount
WHERE account_id = @acc_id;
ELSE IF @operation = 'CREDIT'
UPDATE dbo.accounts
SET balance = balance + @amount
WHERE account_id = @acc_id;
-- Unlock account
UPDATE dbo.accounts
SET is_locked = 0,
    locked_by_tx = NULL
WHERE account_id = @acc_id;
-- Cập nhật status thành COMMITTED
UPDATE dbo.transaction_log
SET status = 'COMMITTED'
WHERE transaction_id = @tx_id;
COMMIT;
PRINT 'COMMIT successful!';
END
ELSE BEGIN PRINT 'No PREPARED transaction found!';
ROLLBACK;
END
GO -- =============================================
    -- 7. TEST: Mô phỏng ROLLBACK phase
    -- =============================================
DECLARE @tx_id VARCHAR(100) = 'TX-TEST-002';
BEGIN TRANSACTION;
-- Lấy thông tin transaction
DECLARE @acc_id VARCHAR(50);
SELECT @acc_id = account_id
FROM dbo.transaction_log
WHERE transaction_id = @tx_id
    AND status = 'PREPARED';
IF @acc_id IS NOT NULL BEGIN -- Unlock account (không thay đổi balance)
UPDATE dbo.accounts
SET is_locked = 0,
    locked_by_tx = NULL
WHERE account_id = @acc_id;
-- Cập nhật status thành ABORTED
UPDATE dbo.transaction_log
SET status = 'ABORTED'
WHERE transaction_id = @tx_id;
COMMIT;
PRINT 'ROLLBACK successful!';
END
ELSE BEGIN PRINT 'No PREPARED transaction found!';
ROLLBACK;
END
GO -- =============================================
    -- 8. TEST: Reset dữ liệu test
    -- =============================================
    -- Unlock tất cả accounts
UPDATE dbo.accounts
SET is_locked = 0,
    locked_by_tx = NULL;
-- Xóa transaction log test
DELETE FROM dbo.transaction_log
WHERE transaction_id LIKE 'TX-TEST-%';
-- Reset balance về ban đầu
UPDATE dbo.accounts
SET balance = 10000000.00
WHERE account_id = 'ACC001';
SELECT *
FROM dbo.accounts;
GO