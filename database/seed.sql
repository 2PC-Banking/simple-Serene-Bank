-- =============================================
-- Seed Data for Bank System (2PC)
-- =============================================

USE BankDB;
GO

-- Xóa dữ liệu cũ (nếu có)
DELETE FROM dbo.transaction_log;
DELETE FROM dbo.accounts;
GO

-- =============================================
-- Thêm dữ liệu mẫu cho bảng ACCOUNTS
-- =============================================
INSERT INTO dbo.accounts (account_id, account_name, balance, is_locked, locked_by_tx)
VALUES 
    ('ACC001', N'Nguyễn Văn A', 10000000.00, 0, NULL),
    ('ACC002', N'Trần Thị B', 5000000.00, 0, NULL),
    ('ACC003', N'Lê Văn C', 15000000.00, 0, NULL),
    ('ACC004', N'Phạm Thị D', 8000000.00, 0, NULL),
    ('ACC005', N'Hoàng Văn E', 20000000.00, 0, NULL);
GO

-- Kiểm tra dữ liệu
SELECT * FROM dbo.accounts;
GO

PRINT 'Seed data inserted successfully!';
GO
