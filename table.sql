-- 1. 删除旧数据库
DROP DATABASE IF EXISTS library_system;
-- 2. 创建新数据库
CREATE DATABASE library_system;
USE library_system;

-- ============================================
-- 3. 创建所有表
-- ============================================

CREATE TABLE Book (
    bid CHAR(8) PRIMARY KEY COMMENT '图书号',
    bname VARCHAR(100) NOT NULL COMMENT '书名',
    author VARCHAR(50) COMMENT '作者',
    price DECIMAL(8,2) COMMENT '价格',
    bstatus INT DEFAULT 0 COMMENT '0-可借 1-已借出 2-已预约',
    borrow_Times INT DEFAULT 0 COMMENT '总借阅次数',
    reserve_Times INT DEFAULT 0 COMMENT '当前预约人数（仅等待状态）'
);

CREATE TABLE Student (
    sid CHAR(8) PRIMARY KEY COMMENT '学生号',
    sname VARCHAR(20) NOT NULL COMMENT '姓名',
    student_no VARCHAR(20) NOT NULL UNIQUE COMMENT '学号',
    password VARCHAR(255) NOT NULL COMMENT '密码',
    arrears DECIMAL(8,2) DEFAULT 0 COMMENT '欠费金额'
);

CREATE TABLE Admin (
    aid CHAR(8) PRIMARY KEY COMMENT '管理员号',
    aname VARCHAR(20) NOT NULL COMMENT '姓名',
    password VARCHAR(255) NOT NULL COMMENT '密码'
);

CREATE TABLE Borrow (
    borrow_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '借阅ID',
    book_ID CHAR(8) NOT NULL,
    student_ID CHAR(8) NOT NULL,
    borrow_Date DATE DEFAULT (CURDATE()),
    due_Date DATE NOT NULL,
    return_Date DATE,
    FOREIGN KEY (book_ID) REFERENCES Book(bid) ON DELETE CASCADE,
    FOREIGN KEY (student_ID) REFERENCES Student(sid) ON DELETE CASCADE,
    INDEX idx_borrow_student (student_ID),
    INDEX idx_borrow_book (book_ID),
    INDEX idx_borrow_return (return_Date)
);

-- 预约表：存储所有预约历史，不物理删除
CREATE TABLE Reserve (
    reserve_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '预约ID',
    book_ID CHAR(8) NOT NULL,
    student_ID CHAR(8) NOT NULL,
    reserve_Date DATE DEFAULT (CURDATE()),
    take_Date DATE COMMENT '实际取书日期',
    status INT DEFAULT 0 COMMENT '0-等待 1-已取书 2-已取消 3-过期',
    FOREIGN KEY (book_ID) REFERENCES Book(bid) ON DELETE CASCADE,
    FOREIGN KEY (student_ID) REFERENCES Student(sid) ON DELETE CASCADE,
    INDEX idx_reserve_book (book_ID),
    INDEX idx_reserve_student (student_ID),
    INDEX idx_reserve_status (status)
);

CREATE TABLE Overdue (
    overdue_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '逾期ID',
    student_ID CHAR(8) NOT NULL,
    book_ID CHAR(8) NOT NULL,
    create_Date DATE DEFAULT (CURDATE()),
    overdue_days INT NOT NULL,
    fine_amount DECIMAL(8,2) NOT NULL,
    is_paid INT DEFAULT 0,
    paid_Date DATE,
    FOREIGN KEY (student_ID) REFERENCES Student(sid) ON DELETE CASCADE,
    FOREIGN KEY (book_ID) REFERENCES Book(bid) ON DELETE CASCADE,
    INDEX idx_overdue_student (student_ID),
    INDEX idx_overdue_paid (is_paid)
);

CREATE TABLE Media (
     media_id INT PRIMARY KEY AUTO_INCREMENT,
     filename VARCHAR(255) NOT NULL,
     filetype VARCHAR(50),
     filepath VARCHAR(500),
     upload_date DATE DEFAULT (CURDATE()),
     uploader VARCHAR(50)
);
-- ============================================
-- 4. 存储过程和函数
-- ============================================

-- 计算罚款函数
DELIMITER //
CREATE FUNCTION CalcFine(due_date DATE, return_date DATE) 
RETURNS DECIMAL(8,2)
DETERMINISTIC
BEGIN
    IF return_date IS NULL OR return_date <= due_date THEN
        RETURN 0;
    END IF;
    RETURN DATEDIFF(return_date, due_date) * 0.5;
END //
DELIMITER ;

DROP PROCEDURE IF EXISTS BorrowBook;
-- 借书存储过程（集成预约取书）
DELIMITER //
CREATE PROCEDURE BorrowBook(
    IN p_sid CHAR(8),
    IN p_bid CHAR(8)
)
main_proc: BEGIN
    DECLARE v_arrears DECIMAL(8,2);
    DECLARE v_count INT DEFAULT 0;
    DECLARE v_status INT DEFAULT 0;
    DECLARE v_reserve_id INT DEFAULT 0;
    DECLARE v_left_reserve INT DEFAULT 0;
	DECLARE v_already_borrowed INT DEFAULT 0;
    DECLARE v_global_borrowed INT DEFAULT 0; 
    
    START TRANSACTION;

    -- 欠费检查
    SELECT arrears INTO v_arrears FROM Student WHERE sid = p_sid FOR UPDATE;
    IF v_arrears >= 10 THEN
        ROLLBACK;
        SELECT '借阅失败：欠费已达10元' AS msg;
        LEAVE main_proc;
    END IF;

    -- 借阅数量检查
    SELECT COUNT(*) INTO v_count FROM Borrow
    WHERE student_ID = p_sid AND return_Date IS NULL FOR UPDATE;
    IF v_count >= 5 THEN
        ROLLBACK;
        SELECT '借阅失败：最多借5本' AS msg;
        LEAVE main_proc;
    END IF;

	SELECT COUNT(*) INTO v_already_borrowed FROM Borrow
    WHERE student_ID = p_sid AND book_ID = p_bid AND return_Date IS NULL;
    IF v_already_borrowed > 0 THEN
        ROLLBACK;
        SELECT '借阅失败：您已经借阅了这本书，尚未归还' AS msg;
        LEAVE main_proc;
    END IF;
    
    SELECT COUNT(*) INTO v_global_borrowed FROM Borrow
    WHERE book_ID = p_bid AND return_Date IS NULL;
    IF v_global_borrowed > 0 THEN
        ROLLBACK;
        SELECT '借阅失败：该书尚未归还，请等待归还后再借阅' AS msg;
        LEAVE main_proc;
    END IF;
    
    -- 图书状态
    SELECT bstatus INTO v_status FROM Book WHERE bid = p_bid FOR UPDATE;

    -- 检查本人是否有等待预约（status=0）
    SELECT reserve_id INTO v_reserve_id FROM Reserve
    WHERE student_ID = p_sid AND book_ID = p_bid AND status = 0
    LIMIT 1 FOR UPDATE;

    -- 规则1：图书已借出(1)且当前用户无预约 → 拒绝
    IF v_status = 1 AND v_reserve_id = 0 THEN
        ROLLBACK;
        SELECT '借阅失败：图书已借出，请先预约' AS msg;
        LEAVE main_proc;
    END IF;

    -- 规则2：图书已预约(2)且当前用户无预约 → 拒绝
    IF v_status = 2 AND v_reserve_id = 0 THEN
        ROLLBACK;
        SELECT '借阅失败：已有他人预约' AS msg;
        LEAVE main_proc;
    END IF;

    -- 规则3：图书已借出(1)且当前用户有预约 → 需等待归还
    IF v_status = 1 AND v_reserve_id > 0 THEN
        ROLLBACK;
        SELECT '借阅失败：该书尚未归还，请等待图书归还后再来取书' AS msg;
        LEAVE main_proc;
    END IF;
    
    -- 规则4：同一天重复借阅检查 → 拒绝
    IF EXISTS (SELECT 1 FROM Borrow WHERE student_ID = p_sid AND book_ID = p_bid AND borrow_Date = CURDATE()) THEN
        ROLLBACK;
        SELECT '借阅失败：今天已借过同一本书' AS msg;
        LEAVE main_proc;
    END IF;

    -- 执行借阅
    INSERT INTO Borrow(book_ID, student_ID, borrow_Date, due_Date)
    VALUES (p_bid, p_sid, CURDATE(), CURDATE() + INTERVAL 30 DAY);

    -- 若本人有等待预约，则更新状态为“已取书”
    IF v_reserve_id > 0 THEN
        UPDATE Reserve SET status = 1, take_Date = CURDATE()
        WHERE reserve_id = v_reserve_id;
    END IF;

    -- 检查该书是否还有其他等待预约
    SELECT COUNT(*) INTO v_left_reserve FROM Reserve
    WHERE book_ID = p_bid AND status = 0;

    -- 更新图书状态：如果还有预约，状态为2；否则为1（已借出）
    UPDATE Book SET borrow_Times = borrow_Times + 1 WHERE bid = p_bid;
    IF v_left_reserve > 0 THEN
        UPDATE Book SET bstatus = 2 WHERE bid = p_bid;
    ELSE
        UPDATE Book SET bstatus = 1 WHERE bid = p_bid;
    END IF;

    COMMIT;
    SELECT '借阅成功' AS msg;
END main_proc //
DELIMITER ;

-- 还书存储过程（不处理预约，只还书，图书状态由触发器自动更新）
DELIMITER //
CREATE PROCEDURE ReturnBook(IN p_borrow_id INT)
BEGIN
    DECLARE v_book_id CHAR(8);
    START TRANSACTION;

    UPDATE Borrow SET return_Date = CURDATE()
    WHERE borrow_id = p_borrow_id AND return_Date IS NULL;

    IF ROW_COUNT() = 0 THEN
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '该借阅记录已归还或不存在';
    END IF;

    -- 获取图书编号（用于后面的触发器自动更新状态）
    SELECT book_ID INTO v_book_id FROM Borrow WHERE borrow_id = p_borrow_id;

    COMMIT;
END //
DELIMITER ;

-- 手动处理预约取消或过期（管理员或定时任务调用）
DELIMITER //
CREATE PROCEDURE UpdateReserveStatus(
    IN p_reserve_id INT,
    IN p_new_status INT   -- 2-取消 3-过期
)
BEGIN
    DECLARE v_current_status INT;
    START TRANSACTION;
    SELECT status INTO v_current_status FROM Reserve WHERE reserve_id = p_reserve_id FOR UPDATE;
    IF v_current_status = 0 THEN
        UPDATE Reserve SET status = p_new_status WHERE reserve_id = p_reserve_id;
        -- 触发器会自动更新 Book 表的 reserve_Times 和 bstatus
        COMMIT;
        SELECT '预约状态已更新' AS msg;
    ELSE
        ROLLBACK;
        SELECT '只有等待中的预约才能修改状态' AS msg;
    END IF;
END //
DELIMITER ;

-- ============================================
-- 5. 触发器
-- ============================================

DROP TRIGGER IF EXISTS trg_after_return;
DELIMITER //
CREATE TRIGGER trg_after_return
AFTER UPDATE ON Borrow
FOR EACH ROW
BEGIN
    DECLARE v_fine DECIMAL(8,2);
    DECLARE v_waiting INT DEFAULT 0;

    -- 处理归还动作（原来为NULL，现在变为非NULL）
    IF NEW.return_Date IS NOT NULL AND OLD.return_Date IS NULL THEN
        -- 计算罚款
        SET v_fine = CalcFine(NEW.due_Date, NEW.return_Date);
        IF v_fine > 0 THEN
            INSERT INTO Overdue(student_ID, book_ID, overdue_days, fine_amount)
            VALUES (NEW.student_ID, NEW.book_ID,
                    DATEDIFF(NEW.return_Date, NEW.due_Date), v_fine);
            UPDATE Student SET arrears = arrears + v_fine
            WHERE sid = NEW.student_ID;
        END IF;

        -- 更新图书状态：检查该书是否有等待中的预约（status=0）
        SELECT COUNT(*) INTO v_waiting FROM Reserve
        WHERE book_ID = NEW.book_ID AND status = 0;

        IF v_waiting > 0 THEN
            UPDATE Book SET bstatus = 2 WHERE bid = NEW.book_ID;
        ELSE
            UPDATE Book SET bstatus = 0 WHERE bid = NEW.book_ID;
        END IF;
    END IF;
END //
DELIMITER ;

-- 新增预约（status=0）时增加图书预约人数，若图书为可借状态则改为已预约
DELIMITER //
CREATE TRIGGER trg_reserve_insert
AFTER INSERT ON Reserve
FOR EACH ROW
BEGIN
    IF NEW.status = 0 THEN
        UPDATE Book SET reserve_Times = reserve_Times + 1 WHERE bid = NEW.book_ID;
        -- 如果图书当前是可借(0)或已借出(1)，但有了预约就改为已预约(2)
        UPDATE Book SET bstatus = 2 WHERE bid = NEW.book_ID AND bstatus IN (0,1);
    END IF;
END //
DELIMITER ;

-- 预约状态更新时（从0变为其他值）减少预约人数，并重新评估图书状态
DELIMITER //
CREATE TRIGGER trg_reserve_status_update
AFTER UPDATE ON Reserve
FOR EACH ROW
BEGIN
    DECLARE left_reserve INT DEFAULT 0;
    IF OLD.status = 0 AND NEW.status != 0 THEN
        -- 预约人数减1
        UPDATE Book SET reserve_Times = GREATEST(reserve_Times - 1, 0)
        WHERE bid = NEW.book_ID;

        -- 检查该书是否还有等待中的预约
        SELECT COUNT(*) INTO left_reserve FROM Reserve
        WHERE book_ID = NEW.book_ID AND status = 0;

        -- 如果没有等待预约了，根据是否有未还借阅决定图书状态
        IF left_reserve = 0 THEN
            IF EXISTS (SELECT 1 FROM Borrow WHERE book_ID = NEW.book_ID AND return_Date IS NULL) THEN
                UPDATE Book SET bstatus = 1 WHERE bid = NEW.book_ID; -- 已借出
            ELSE
                UPDATE Book SET bstatus = 0 WHERE bid = NEW.book_ID; -- 可借
            END IF;
        END IF;
    END IF;
END //
DELIMITER ;

-- ============================================
-- 6. 插入测试数据
-- ============================================

-- 管理员
INSERT INTO Admin (aid, aname, password) VALUES ('A001', 'Tom', '123456');

-- 学生
INSERT INTO Student (sid, sname, student_no, password, arrears) VALUES 
('S001', 'Rose',  '20260001', '123456', 0), 
('S002', 'John',  '20260002', '123456', 5), 
('S003', 'Alice', '20260003', '123456', 0), 
('S004', 'Bob',   '20260004', '123456', 10), 
('S005', 'Cindy', '20260005', '123456', 0), 
('S006', 'David', '20260006', '123456', 0), 
('S007', 'Eva',   '20260007', '123456', 0);

-- 图书
INSERT INTO Book(bid, bname, author, price, bstatus, borrow_Times, reserve_Times) VALUES 
('B001', 'Database System Concepts', 'Silberschatz', 68.0, 1, 3, 0), 
('B002', 'Harry Potter and the Sorcerer''s Stone', 'J.K.Rowling', 59.0, 0, 3, 0), 
('B003', 'Harry Potter and the Chamber of Secrets', 'J.K.Rowling', 62.0, 0, 2, 0), 
('B004', 'Operating System Concepts', 'Silberschatz', 75.0, 1, 3, 0), 
('B005', 'Computer Networks', 'Kurose', 66.0, 0, 3, 0), 
('B006', 'Advanced SQL Programming', 'Silberschatz', 72.0, 0, 3, 0), 
('B007', 'Data Mining: Concepts and Techniques', 'Jiawei Han', 88.0, 0, 0, 0), 
('B008', 'MySQL 8 Cookbook', 'A. Pachev', 79.0, 0, 0, 0), 
('B009', 'Learning MySQL', 'Paul DuBois', 56.0, 1, 2, 0), 
('B010', 'SQL Performance Explained', 'Markus Winand', 70.0, 0, 2, 0);

-- 借阅记录
INSERT INTO Borrow(book_ID, student_ID, borrow_Date, due_Date, return_Date) VALUES 
-- B001 未还（S001）
('B001', 'S001', '2026-05-20', '2026-06-19', NULL),
-- B004 未还（S001）
('B004', 'S001', '2026-05-25', '2026-06-24', NULL),
-- B009 未还（S006）
('B009', 'S006', '2026-05-22', '2026-06-21', NULL),
-- 其他已还记录（用于历史）
('B001', 'S002', '2024-01-10', '2024-02-09', '2024-01-20'),
('B002', 'S002', '2024-03-01', '2024-03-31', '2024-03-20'),
('B002', 'S003', '2024-12-01', '2024-12-31', '2024-12-15'),
('B002', 'S004', '2024-10-10', '2024-11-09', '2024-10-18'),
('B003', 'S001', '2024-02-15', '2024-03-16', '2024-02-28'),
('B003', 'S004', '2023-12-05', '2024-01-04', '2023-12-15'),
('B004', 'S003', '2024-06-06', '2024-07-06', '2024-06-15'),
('B005', 'S003', '2024-02-01', '2024-03-02', '2024-02-10'),
('B005', 'S001', '2024-04-20', '2024-05-20', '2024-04-30'),
('B005', 'S002', '2024-05-12', '2024-06-11', '2024-05-25'),
('B006', 'S005', '2023-11-10', '2023-12-10', '2023-11-25'),
('B006', 'S006', '2024-01-15', '2024-02-14', '2024-01-25'),
('B006', 'S002', '2024-11-02', '2024-12-02', '2024-11-18'),
('B009', 'S006', '2024-03-20', '2024-04-19', '2024-03-30'),
('B010', 'S006', '2024-08-08', '2024-09-07', '2024-08-16'),
('B010', 'S002', '2024-09-01', '2024-10-01', '2024-09-12');

-- 逾期记录（使 S002 欠费5元，S004 欠费10元）
INSERT INTO Overdue (student_ID, book_ID, create_Date, overdue_days, fine_amount, is_paid, paid_Date) VALUES 
('S002', 'B001', '2024-02-21', 10, 5.00, 0, NULL),
('S004', 'B002', '2024-12-20', 20, 10.00, 0, NULL);

-- 预约记录（仅针对当前被借出的图书 B001、B004、B009，且均为等待状态，take_Date 为 NULL）
INSERT INTO Reserve(book_ID, student_ID, reserve_Date, take_Date, status) VALUES 
('B009', 'S001', '2026-05-31', NULL, 0),
('B001', 'S002', '2026-05-29', NULL, 0),
('B001', 'S003', '2026-05-30', NULL, 0),
('B004', 'S006', '2026-05-28', NULL, 0);

-- ============================================
-- 7. 验证数据
-- ============================================
SELECT '=== 管理员 ===' AS ''; SELECT * FROM Admin;
SELECT '=== 学生 ===' AS ''; SELECT * FROM Student;
SELECT '=== 图书 ===' AS ''; SELECT * FROM Book;
SELECT '=== 借阅（未还）===' AS ''; SELECT * FROM Borrow WHERE return_Date IS NULL;
SELECT '=== 预约（等待）===' AS ''; SELECT * FROM Reserve WHERE status = 0;
SELECT '=== 逾期未缴 ===' AS ''; SELECT * FROM Overdue WHERE is_paid = 0;

SET FOREIGN_KEY_CHECKS = 0;
SET SQL_SAFE_UPDATES = 0;

DELETE FROM Overdue WHERE overdue_id > 0;
DELETE FROM Reserve WHERE reserve_id > 0;
DELETE FROM Borrow WHERE borrow_id > 0;
DELETE FROM Book WHERE bid IS NOT NULL;
DELETE FROM Student WHERE sid IS NOT NULL;
DELETE FROM Admin WHERE aid IS NOT NULL;

SET SQL_SAFE_UPDATES = 1;
SET FOREIGN_KEY_CHECKS = 1;

UPDATE Student 
SET arrears = 10 
WHERE sid = 'S004';


INSERT INTO Overdue (student_ID, book_ID, create_Date, overdue_days, fine_amount, is_paid, paid_Date) 
VALUES ('S004', 'B002', '2024-12-20', 20, 10.00, 0, NULL);