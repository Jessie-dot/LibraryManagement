import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import mysql.connector
from mysql.connector import Error
import os
import shutil
from datetime import datetime
from PIL import Image, ImageTk
import subprocess
import sys

# ----------------------------- 数据库配置 ---------------------------------
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'database': 'library_system',
    'autocommit': False
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def init_media_table():
    """创建媒体文件表（如果不存在）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Media (
            media_id INT PRIMARY KEY AUTO_INCREMENT,
            filename VARCHAR(255) NOT NULL,
            filetype VARCHAR(50),
            filepath VARCHAR(500),
            upload_date DATE DEFAULT (CURDATE()),
            uploader VARCHAR(50)
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# ----------------------------- 登录窗口 ---------------------------------
class LoginWindow:
    def __init__(self, master):
        self.master = master
        self.master.title("图书馆管理系统登录")
        self.master.geometry("400x300")
        self.center_window()
        self.create_widgets()

    def center_window(self):
        self.master.update_idletasks()
        w = self.master.winfo_width()
        h = self.master.winfo_height()
        x = (self.master.winfo_screenwidth() // 2) - (w // 2)
        y = (self.master.winfo_screenheight() // 2) - (h // 2)
        self.master.geometry(f"{w}x{h}+{x}+{y}")

    def create_widgets(self):
        tk.Label(self.master, text="登录角色", font=("Arial", 12)).pack(pady=10)
        self.role_var = tk.StringVar(value="student")
        tk.Radiobutton(self.master, text="学生", variable=self.role_var, value="student").pack()
        tk.Radiobutton(self.master, text="管理员", variable=self.role_var, value="admin").pack()

        tk.Label(self.master, text="账号", font=("Arial", 12)).pack(pady=5)
        self.username_entry = tk.Entry(self.master, width=25)
        self.username_entry.pack()

        tk.Label(self.master, text="密码", font=("Arial", 12)).pack(pady=5)
        self.password_entry = tk.Entry(self.master, show="*", width=25)
        self.password_entry.pack()

        tk.Button(self.master, text="登录", command=self.login, width=15).pack(pady=10)
        tk.Button(self.master, text="学生注册", command=self.register, width=15).pack()

    def login(self):
        role = self.role_var.get()
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showerror("错误", "账号和密码不能为空")
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        if role == "student":
            cursor.execute("SELECT sid, sname, password FROM Student WHERE student_no = %s", (username,))
            row = cursor.fetchone()
            if row and row[2] == password:
                self.master.destroy()
                root = tk.Tk()
                StudentMainWindow(root, row[0], row[1])
                root.mainloop()
            else:
                messagebox.showerror("错误", "学号或密码错误")
        else:
            cursor.execute("SELECT aid, aname, password FROM Admin WHERE aid = %s", (username,))
            row = cursor.fetchone()
            if row and row[2] == password:
                self.master.destroy()
                root = tk.Tk()
                AdminMainWindow(root, row[0], row[1])
                root.mainloop()
            else:
                messagebox.showerror("错误", "管理员号或密码错误")
        cursor.close()
        conn.close()

    def register(self):
        RegisterDialog(self.master)

class RegisterDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("学生注册")
        self.geometry("300x250")
        self.parent = parent
        self.create_widgets()
        self.center_window()

    def center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def create_widgets(self):
        tk.Label(self, text="姓名").pack(pady=5)
        self.name_entry = tk.Entry(self)
        self.name_entry.pack()
        tk.Label(self, text="学号").pack(pady=5)
        self.no_entry = tk.Entry(self)
        self.no_entry.pack()
        tk.Label(self, text="密码").pack(pady=5)
        self.pwd_entry = tk.Entry(self, show="*")
        self.pwd_entry.pack()
        tk.Button(self, text="注册", command=self.do_register).pack(pady=10)

    def do_register(self):
        name = self.name_entry.get().strip()
        student_no = self.no_entry.get().strip()
        pwd = self.pwd_entry.get().strip()
        if not name or not student_no or not pwd:
            messagebox.showerror("错误", "所有字段都不能为空")
            return
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT sid FROM Student WHERE student_no = %s", (student_no,))
        if cursor.fetchone():
            messagebox.showerror("错误", "学号已存在")
            cursor.close()
            conn.close()
            return
        cursor.execute("SELECT MAX(CAST(SUBSTRING(sid,2) AS UNSIGNED)) FROM Student")
        max_id = cursor.fetchone()[0] or 0
        new_id = f"S{max_id+1:03d}"
        cursor.execute("INSERT INTO Student(sid, sname, student_no, password, arrears) VALUES (%s,%s,%s,%s,0)",
                       (new_id, name, student_no, pwd))
        conn.commit()
        messagebox.showinfo("成功", f"注册成功！您的学生号为 {new_id}")
        self.destroy()
        cursor.close()
        conn.close()

# ----------------------------- 学生端主窗口 ---------------------------------
class StudentMainWindow:
    def __init__(self, master, sid, sname):
        self.master = master
        self.sid = sid
        self.sname = sname
        self.master.title(f"学生端 - {sname}")
        self.master.geometry("1000x700")
        self.create_menu()
        self.create_main_frame()
        self.show_welcome()

    def create_menu(self):
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)

        book_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="图书", menu=book_menu)
        book_menu.add_command(label="图书查询", command=self.show_book_search)
        book_menu.add_command(label="我的借阅", command=self.show_my_borrow)
        book_menu.add_command(label="我的预约", command=self.show_my_reserves)

        account_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="账户", menu=account_menu)
        account_menu.add_command(label="逾期与罚款", command=self.show_overdue)
        account_menu.add_command(label="个人中心", command=self.show_profile)
        account_menu.add_command(label="退出登录", command=self.logout)

        media_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="媒体库", menu=media_menu)
        media_menu.add_command(label="上传文件", command=self.upload_media)
        media_menu.add_command(label="查看媒体", command=self.show_media_gallery)

    def create_main_frame(self):
        self.main_frame = tk.Frame(self.master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def show_welcome(self):
        self.clear_frame()
        tk.Label(self.main_frame, text=f"欢迎 {self.sname}", font=("Arial", 20)).pack(pady=50)

    # ----------------------------- 图书查询 ---------------------------------
    def show_book_search(self):
        self.clear_frame()
        frame = self.main_frame
        tk.Label(frame, text="图书查询", font=("Arial", 16)).pack(pady=10)

        search_frame = tk.Frame(frame)
        search_frame.pack(pady=10)
        tk.Label(search_frame, text="关键词:").pack(side=tk.LEFT)
        self.keyword_entry = tk.Entry(search_frame, width=20)
        self.keyword_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(search_frame, text="类型:").pack(side=tk.LEFT)
        self.search_type = ttk.Combobox(search_frame, values=["书名", "作者", "图书号"], width=8)
        self.search_type.current(0)
        self.search_type.pack(side=tk.LEFT, padx=5)
        tk.Button(search_frame, text="搜索", command=self.do_search).pack(side=tk.LEFT)

        self.book_tree = ttk.Treeview(frame, columns=("bid","bname","author","price","bstatus","borrow_Times","reserve_Times"), show="headings", height=15)
        for col in ("bid","bname","author","price","bstatus","borrow_Times","reserve_Times"):
            self.book_tree.heading(col, text=col)
        self.book_tree.pack(pady=10, fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="查看详情", command=self.show_book_detail).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="借阅", command=self.borrow_book).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="预约", command=self.reserve_book).pack(side=tk.LEFT, padx=5)

        self.do_search()

    def do_search(self):
        if not hasattr(self, 'keyword_entry') or not self.keyword_entry.winfo_exists():
            return
        keyword = self.keyword_entry.get().strip()
        stype = self.search_type.get()
        conn = get_db_connection()
        cursor = conn.cursor()
        if stype == "书名":
            cursor.execute("SELECT bid,bname,author,price,bstatus,borrow_Times,reserve_Times FROM Book WHERE bname LIKE %s", (f"%{keyword}%",))
        elif stype == "作者":
            cursor.execute("SELECT bid,bname,author,price,bstatus,borrow_Times,reserve_Times FROM Book WHERE author LIKE %s", (f"%{keyword}%",))
        else:
            cursor.execute("SELECT bid,bname,author,price,bstatus,borrow_Times,reserve_Times FROM Book WHERE bid = %s", (keyword,))
        rows = cursor.fetchall()
        self.book_tree.delete(*self.book_tree.get_children())
        status_map = {0:"可借",1:"已借出",2:"已预约"}
        for row in rows:
            display = list(row)
            display[4] = status_map.get(row[4], "未知")
            self.book_tree.insert("", tk.END, values=display)
        cursor.close()
        conn.close()

    def show_book_detail(self):
        selected = self.book_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一本书")
            return
        bid = self.book_tree.item(selected[0])['values'][0]
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Book WHERE bid = %s", (bid,))
        book = cursor.fetchone()
        cursor.close()
        conn.close()
        if book:
            status_map = {0:"可借",1:"已借出",2:"已预约"}
            detail = f"图书号: {book['bid']}\n书名: {book['bname']}\n作者: {book['author']}\n价格: {book['price']}\n状态: {status_map[book['bstatus']]}\n总借阅次数: {book['borrow_Times']}\n当前预约人数: {book['reserve_Times']}"
            messagebox.showinfo("图书详情", detail)

    def borrow_book(self):
        selected = self.book_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一本书")
            return
        bid = self.book_tree.item(selected[0])['values'][0]
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.callproc('BorrowBook', (self.sid, bid))
            for result in cursor.stored_results():
                msg = result.fetchone()[0]
                if "成功" in msg:
                    conn.commit()
                    messagebox.showinfo("成功", msg)
                    self.do_search()
                    self.show_my_borrow()
                else:
                    messagebox.showerror("失败", msg)
        except Error as e:
            conn.rollback()
            messagebox.showerror("错误", str(e))
        finally:
            cursor.close()
            conn.close()

    def reserve_book(self):
        selected = self.book_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一本书")
            return
        bid = self.book_tree.item(selected[0])['values'][0]
        # 检查图书是否已借出（bstatus=1）
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT arrears FROM Student WHERE sid = %s", (self.sid,))
        arrears = cursor.fetchone()[0]
        if arrears >= 10:
            messagebox.showerror("错误", "欠费已达10元，无法预约")
            cursor.close()
            conn.close()
            return
        
        cursor.execute("SELECT bstatus FROM Book WHERE bid = %s", (bid,))
        status = cursor.fetchone()[0]
        if status != 1:
            messagebox.showerror("错误", "只有已借出的图书才能预约")
            cursor.close()
            conn.close()
            return
        # 检查是否已经借阅该书且未归还
        cursor.execute("SELECT COUNT(*) FROM Borrow WHERE student_ID=%s AND book_ID=%s AND return_Date IS NULL", (self.sid, bid))
        if cursor.fetchone()[0] > 0:
            messagebox.showerror("错误", "您已经借阅了这本书，不能重复预约")
            cursor.close()
            conn.close()
            return
        # 检查是否已有等待预约（status=0）
        cursor.execute("SELECT COUNT(*) FROM Reserve WHERE book_ID=%s AND student_ID=%s AND status=0", (bid, self.sid))
        if cursor.fetchone()[0] > 0:
            messagebox.showerror("错误", "您已经预约过这本书了")
            cursor.close()
            conn.close()
            return
        # 插入预约记录（状态0等待）
        try:
            cursor.execute("INSERT INTO Reserve(book_ID, student_ID, reserve_Date, status) VALUES (%s,%s,CURDATE(),0)",
                           (bid, self.sid))
            conn.commit()
            messagebox.showinfo("成功", "预约成功！请等待通知取书。")
            self.do_search()
            self.show_my_reserves()
        except Error as e:
            conn.rollback()
            messagebox.showerror("错误", str(e))
        finally:
            cursor.close()
            conn.close()

    # ----------------------------- 我的借阅 ---------------------------------
    def show_my_borrow(self):
        self.clear_frame()
        frame = self.main_frame
        tk.Label(frame, text="我的借阅", font=("Arial", 16)).pack(pady=10)
        tree = ttk.Treeview(frame, columns=("bid","bname","borrow_Date","due_Date","status"), show="headings", height=15)
        tree.heading("bid", text="图书号")
        tree.heading("bname", text="书名")
        tree.heading("borrow_Date", text="借书日期")
        tree.heading("due_Date", text="应还日期")
        tree.heading("status", text="状态")
        tree.pack(pady=10, fill=tk.BOTH, expand=True)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.bid, b.bname, br.borrow_Date, br.due_Date,
                   CASE WHEN br.return_Date IS NULL THEN '未归还' ELSE '已归还' END
            FROM Borrow br JOIN Book b ON br.book_ID = b.bid
            WHERE br.student_ID = %s
            ORDER BY br.borrow_Date DESC
        """, (self.sid,))
        rows = cursor.fetchall()
        for row in rows:
            tree.insert("", tk.END, values=row)
        cursor.close()
        conn.close()

        def return_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("警告", "请选择要归还的图书")
                return
            bid = tree.item(selected[0])['values'][0]
            conn2 = get_db_connection()
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT borrow_id FROM Borrow WHERE student_ID=%s AND book_ID=%s AND return_Date IS NULL", (self.sid, bid))
            row = cursor2.fetchone()
            if not row:
                messagebox.showerror("错误", "未找到借阅记录")
                cursor2.close()
                conn2.close()
                return
            borrow_id = row[0]
            try:
                cursor2.callproc('ReturnBook', (borrow_id,))
                while cursor2.nextset():   # 清空任何残留结果
                    pass
                conn2.commit()
                messagebox.showinfo("成功", "归还成功")
                self.show_my_borrow()
                self.show_overdue()
            except Error as e:
                conn2.rollback()
                messagebox.showerror("错误", str(e))
            finally:
                cursor2.close()
                conn2.close()

        tk.Button(frame, text="归还所选图书", command=return_selected).pack(pady=5)

    # ----------------------------- 我的预约 ---------------------------------
    def show_my_reserves(self):
        self.clear_frame()
        frame = self.main_frame
        tk.Label(frame, text="我的预约", font=("Arial", 16)).pack(pady=10)
        tree = ttk.Treeview(frame, columns=("bid","bname","reserve_Date","status_text"), show="headings", height=15)
        tree.heading("bid", text="图书号")
        tree.heading("bname", text="书名")
        tree.heading("reserve_Date", text="预约日期")
        tree.heading("status_text", text="状态")
        tree.pack(pady=10, fill=tk.BOTH, expand=True)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.book_ID, b.bname, r.reserve_Date, r.status
            FROM Reserve r JOIN Book b ON r.book_ID = b.bid
            WHERE r.student_ID = %s
            ORDER BY r.reserve_Date DESC
        """, (self.sid,))
        rows = cursor.fetchall()
        status_map = {0:"等待", 1:"已取书", 2:"已取消", 3:"过期"}
        for row in rows:
            tree.insert("", tk.END, values=(row[0], row[1], row[2], status_map[row[3]]))
        cursor.close()
        conn.close()

        def cancel_reserve():
            selected = tree.selection()
            if not selected:
                return
            bid = tree.item(selected[0])['values'][0]
            # 获取 reserve_id
            conn2 = get_db_connection()
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT reserve_id FROM Reserve WHERE student_ID=%s AND book_ID=%s AND status=0", (self.sid, bid))
            row = cursor2.fetchone()
            if not row:
                messagebox.showerror("错误", "未找到等待中的预约")
                cursor2.close()
                conn2.close()
                return
            reserve_id = row[0]
            if messagebox.askyesno("确认", "确定取消预约吗？"):
                try:
                    cursor2.callproc('UpdateReserveStatus', (reserve_id, 2))  # 2=已取消
                    conn2.commit()
                    messagebox.showinfo("成功", "已取消预约")
                    self.show_my_reserves()
                except Error as e:
                    conn2.rollback()
                    messagebox.showerror("错误", str(e))
                finally:
                    cursor2.close()
                    conn2.close()

        tk.Button(frame, text="取消选中预约", command=cancel_reserve).pack(pady=5)

    # ----------------------------- 逾期管理 ---------------------------------
    def show_overdue(self):
        self.clear_frame()
        frame = self.main_frame
        tk.Label(frame, text="逾期记录与罚款", font=("Arial", 16)).pack(pady=10)
        tree = ttk.Treeview(frame, columns=("bid","bname","overdue_days","fine_amount","is_paid"), show="headings", height=10)
        tree.heading("bid", text="图书号")
        tree.heading("bname", text="书名")
        tree.heading("overdue_days", text="逾期天数")
        tree.heading("fine_amount", text="罚款金额")
        tree.heading("is_paid", text="是否缴纳")
        tree.pack(pady=10, fill=tk.BOTH, expand=True)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.book_ID, b.bname, o.overdue_days, o.fine_amount,
                   CASE WHEN o.is_paid=1 THEN '已缴' ELSE '未缴' END
            FROM Overdue o JOIN Book b ON o.book_ID = b.bid
            WHERE o.student_ID = %s
        """, (self.sid,))
        rows = cursor.fetchall()
        for row in rows:
            tree.insert("", tk.END, values=row)
        cursor.close()
        conn.close()

        conn2 = get_db_connection()
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT arrears FROM Student WHERE sid=%s", (self.sid,))
        arrears = cursor2.fetchone()[0]
        tk.Label(frame, text=f"当前总欠费: {arrears} 元", font=("Arial", 12)).pack(pady=5)
        cursor2.close()
        conn2.close()

        def pay_fines():
            if arrears <= 0:
                messagebox.showinfo("提示", "没有欠费")
                return
            if messagebox.askyesno("确认缴费", f"您当前欠费 {arrears} 元，确认缴纳全部罚款吗？"):
                conn3 = get_db_connection()
                cursor3 = conn3.cursor()
                try:
                    cursor3.execute("UPDATE Overdue SET is_paid=1, paid_Date=CURDATE() WHERE student_ID=%s AND is_paid=0", (self.sid,))
                    cursor3.execute("UPDATE Student SET arrears=0 WHERE sid=%s", (self.sid,))
                    conn3.commit()
                    messagebox.showinfo("成功", "缴费成功")
                    self.show_overdue()
                except Exception as e:
                    conn3.rollback()
                    messagebox.showerror("错误", str(e))
                finally:
                    cursor3.close()
                    conn3.close()

        tk.Button(frame, text="缴纳全部罚款", command=pay_fines).pack(pady=5)

    # ----------------------------- 个人中心 ---------------------------------
    def show_profile(self):
        self.clear_frame()
        frame = self.main_frame
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT sid, sname, student_no, arrears FROM Student WHERE sid=%s", (self.sid,))
        info = cursor.fetchone()
        cursor.close()
        conn.close()

        tk.Label(frame, text="个人信息", font=("Arial", 16)).pack(pady=10)
        tk.Label(frame, text=f"学生号: {info['sid']}").pack()
        tk.Label(frame, text=f"姓名: {info['sname']}").pack()
        tk.Label(frame, text=f"学号: {info['student_no']}").pack()
        tk.Label(frame, text=f"欠费: {info['arrears']} 元").pack()

        def modify_password():
            new_pwd = simpledialog.askstring("修改密码", "请输入新密码", show='*')
            if new_pwd:
                conn2 = get_db_connection()
                cursor2 = conn2.cursor()
                cursor2.execute("UPDATE Student SET password=%s WHERE sid=%s", (new_pwd, self.sid))
                conn2.commit()
                cursor2.close()
                conn2.close()
                messagebox.showinfo("成功", "密码已修改")

        tk.Button(frame, text="修改密码", command=modify_password).pack(pady=5)

    def logout(self):
        self.master.destroy()
        root = tk.Tk()
        LoginWindow(root)
        root.mainloop()

    # ----------------------------- 媒体管理 ---------------------------------
    def upload_media(self):
        file_path = filedialog.askopenfilename(title="选择文件")
        if not file_path:
            return
        filename = os.path.basename(file_path)
        ext = filename.split('.')[-1].lower()
        upload_dir = "uploads"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        dest_path = os.path.join(upload_dir, f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}")
        shutil.copy2(file_path, dest_path)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Media(filename, filetype, filepath, uploader) VALUES (%s, %s, %s, %s)",
                       (filename, ext, dest_path, self.sid))
        conn.commit()
        cursor.close()
        conn.close()
        messagebox.showinfo("成功", f"文件 {filename} 上传成功")

    def show_media_gallery(self):
        self.clear_frame()
        frame = self.main_frame
        canvas = tk.Canvas(frame)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT media_id, filename, filetype, filepath, upload_date FROM Media ORDER BY upload_date DESC")
        medias = cursor.fetchall()
        cursor.close()
        conn.close()

        for media in medias:
            media_id, filename, filetype, filepath, upload_date = media
            frm = tk.Frame(scrollable_frame, bd=1, relief=tk.RAISED)
            frm.pack(pady=5, padx=5, fill=tk.X)

            # 预览图片
            if filetype.lower() in ['jpg','jpeg','png','gif']:
                try:
                    img = Image.open(filepath)
                    img.thumbnail((80,80))
                    photo = ImageTk.PhotoImage(img)
                    lbl_img = tk.Label(frm, image=photo)
                    lbl_img.image = photo
                    lbl_img.pack(side=tk.LEFT, padx=5)
                except:
                    tk.Label(frm, text="[图片预览失败]").pack(side=tk.LEFT, padx=5)
            else:
                tk.Label(frm, text=f"[{filetype.upper()}文件]").pack(side=tk.LEFT, padx=5)

            info_text = f"{filename}\n上传时间: {upload_date}"
            tk.Label(frm, text=info_text, anchor="w").pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

            # 打开文件函数
            def open_file(path=filepath):
                if os.path.exists(path):
                    try:
                        if sys.platform == 'win32':
                            os.startfile(path)
                        elif sys.platform == 'darwin':
                            subprocess.run(['open', path])
                        else:
                            subprocess.run(['xdg-open', path])
                    except:
                        messagebox.showerror("错误", "无法打开文件")
                else:
                    messagebox.showerror("错误", "文件不存在")

            # 删除文件函数
            def delete_media(mid=media_id, path=filepath, fname=filename):
                if messagebox.askyesno("确认删除", f"确定删除文件 {fname} 吗？"):
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM Media WHERE media_id = %s", (mid,))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        if os.path.exists(path):
                            os.remove(path)
                        messagebox.showinfo("成功", "文件已删除")
                        self.show_media_gallery()  # 刷新
                    except Exception as e:
                        messagebox.showerror("错误", str(e))

            btn_frame = tk.Frame(frm)
            btn_frame.pack(side=tk.RIGHT, padx=5)
            tk.Button(btn_frame, text="打开", command=open_file).pack(side=tk.LEFT, padx=2)
            tk.Button(btn_frame, text="删除", command=delete_media).pack(side=tk.LEFT, padx=2)
# ----------------------------- 管理员端主窗口 ---------------------------------
class AdminMainWindow:
    def __init__(self, master, aid, aname):
        self.master = master
        self.aid = aid
        self.aname = aname
        self.master.title(f"管理员端 - {aname}")
        self.master.geometry("1100x750")
        self.create_menu()
        self.create_main_frame()
        self.show_welcome()

    def create_menu(self):
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)

        book_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="图书管理", menu=book_menu)
        book_menu.add_command(label="图书列表", command=self.show_book_manage)
        book_menu.add_command(label="添加图书", command=self.add_book)

        student_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="学生管理", menu=student_menu)
        student_menu.add_command(label="学生列表", command=self.show_student_manage)
        student_menu.add_command(label="添加学生", command=self.add_student)

        borrow_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="借阅/预约", menu=borrow_menu)
        borrow_menu.add_command(label="借阅处理", command=self.show_borrow_handle)
        borrow_menu.add_command(label="预约处理", command=self.show_reserve_handle)

        fine_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="逾期管理", menu=fine_menu)
        fine_menu.add_command(label="逾期记录", command=self.show_overdue_manage)

        media_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="媒体库", menu=media_menu)
        media_menu.add_command(label="上传文件", command=self.upload_media)
        media_menu.add_command(label="查看媒体", command=self.show_media_gallery)

        menubar.add_command(label="退出登录", command=self.logout)

    def create_main_frame(self):
        self.main_frame = tk.Frame(self.master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def show_welcome(self):
        self.clear_frame()
        tk.Label(self.main_frame, text=f"欢迎管理员 {self.aname}", font=("Arial", 20)).pack(pady=50)

    # ----------------------------- 图书管理 ---------------------------------
    def show_book_manage(self):
        self.clear_frame()
        frame = self.main_frame
        tk.Label(frame, text="图书管理", font=("Arial", 16)).pack(pady=10)

        tree = ttk.Treeview(frame, columns=("bid","bname","author","price","bstatus","borrow_Times","reserve_Times"), show="headings", height=15)
        for col in ("bid","bname","author","price","bstatus","borrow_Times","reserve_Times"):
            tree.heading(col, text=col)
        tree.pack(pady=10, fill=tk.BOTH, expand=True)

        def refresh():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT bid,bname,author,price,bstatus,borrow_Times,reserve_Times FROM Book")
            rows = cursor.fetchall()
            tree.delete(*tree.get_children())
            status_map = {0:"可借", 1:"已借出", 2:"已预约"}
            for row in rows:
                # 将第5列（索引4）bstatus 转换为文字
                display_row = list(row)
                display_row[4] = status_map.get(row[4], "未知")
                tree.insert("", tk.END, values=display_row)
            cursor.close()
            conn.close()
        refresh()

        def delete_book():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("警告", "请选择图书")
                return
            bid = tree.item(selected[0])['values'][0]
            if messagebox.askyesno("确认", f"确定删除图书 {bid} 吗？"):
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("DELETE FROM Book WHERE bid=%s", (bid,))
                    conn.commit()
                    refresh()
                except Exception as e:
                    conn.rollback()
                    messagebox.showerror("错误", str(e))
                finally:
                    cursor.close()
                    conn.close()

        def edit_book():
            selected = tree.selection()
            if not selected:
                return
            values = tree.item(selected[0])['values']
            bid = values[0]
            new_name = simpledialog.askstring("修改书名", "新书名:", initialvalue=values[1])
            if new_name is not None:
                new_author = simpledialog.askstring("修改作者", "新作者:", initialvalue=values[2])
                new_price = simpledialog.askfloat("修改价格", "新价格:", initialvalue=values[3])
                if new_price is None:
                    return
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE Book SET bname=%s, author=%s, price=%s WHERE bid=%s", (new_name, new_author, new_price, bid))
                conn.commit()
                cursor.close()
                conn.close()
                refresh()

        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="刷新", command=refresh).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="修改信息", command=edit_book).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="删除", command=delete_book).pack(side=tk.LEFT, padx=5)

    def add_book(self):
        dialog = tk.Toplevel(self.master)
        dialog.title("添加图书")
        dialog.geometry("300x250")
        fields = {}
        tk.Label(dialog, text="图书号").pack(pady=5)
        fields['bid'] = tk.Entry(dialog)
        fields['bid'].pack()
        tk.Label(dialog, text="书名").pack(pady=5)
        fields['bname'] = tk.Entry(dialog)
        fields['bname'].pack()
        tk.Label(dialog, text="作者").pack(pady=5)
        fields['author'] = tk.Entry(dialog)
        fields['author'].pack()
        tk.Label(dialog, text="价格").pack(pady=5)
        fields['price'] = tk.Entry(dialog)
        fields['price'].pack()

        def submit():
            bid = fields['bid'].get().strip()
            bname = fields['bname'].get().strip()
            author = fields['author'].get().strip()
            price = fields['price'].get().strip()
            if not bid or not bname:
                messagebox.showerror("错误", "图书号和书名不能为空")
                return
            try:
                price = float(price)
            except:
                price = 0.0
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO Book(bid,bname,author,price,bstatus,borrow_Times,reserve_Times) VALUES (%s,%s,%s,%s,0,0,0)",
                               (bid, bname, author, price))
                conn.commit()
                messagebox.showinfo("成功", "添加成功")
                dialog.destroy()
                self.show_book_manage()
            except Error as e:
                conn.rollback()
                messagebox.showerror("错误", str(e))
            finally:
                cursor.close()
                conn.close()
        tk.Button(dialog, text="确定", command=submit).pack(pady=10)

    # ----------------------------- 学生管理 ---------------------------------
    def show_student_manage(self):
        self.clear_frame()
        frame = self.main_frame
        tk.Label(frame, text="学生管理", font=("Arial", 16)).pack(pady=10)
        tree = ttk.Treeview(frame, columns=("sid","sname","student_no","arrears"), show="headings", height=15)
        tree.heading("sid", text="学生号")
        tree.heading("sname", text="姓名")
        tree.heading("student_no", text="学号")
        tree.heading("arrears", text="欠费")
        tree.pack(pady=10, fill=tk.BOTH, expand=True)

        def refresh():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT sid, sname, student_no, arrears FROM Student")
            rows = cursor.fetchall()
            tree.delete(*tree.get_children())
            for row in rows:
                tree.insert("", tk.END, values=row)
            cursor.close()
            conn.close()
        refresh()

        def reset_pwd():
            selected = tree.selection()
            if not selected:
                return
            sid = tree.item(selected[0])['values'][0]
            new_pwd = simpledialog.askstring("重置密码", "请输入新密码", show='*')
            if new_pwd:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE Student SET password=%s WHERE sid=%s", (new_pwd, sid))
                conn.commit()
                cursor.close()
                conn.close()
                messagebox.showinfo("成功", "密码已重置")

        def delete_student():
            selected = tree.selection()
            if not selected:
                return
            sid = tree.item(selected[0])['values'][0]
            if messagebox.askyesno("确认", f"确定删除学生 {sid} 吗？会级联删除其借阅预约等记录"):
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("DELETE FROM Student WHERE sid=%s", (sid,))
                    conn.commit()
                    refresh()
                except Exception as e:
                    conn.rollback()
                    messagebox.showerror("错误", str(e))
                finally:
                    cursor.close()
                    conn.close()

        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="刷新", command=refresh).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="重置密码", command=reset_pwd).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="删除学生", command=delete_student).pack(side=tk.LEFT, padx=5)

    def add_student(self):
        dialog = tk.Toplevel(self.master)
        dialog.title("添加学生")
        dialog.geometry("300x250")
        fields = {}
        tk.Label(dialog, text="学生号 (如 S008)").pack(pady=5)
        fields['sid'] = tk.Entry(dialog)
        fields['sid'].pack()
        tk.Label(dialog, text="姓名").pack(pady=5)
        fields['sname'] = tk.Entry(dialog)
        fields['sname'].pack()
        tk.Label(dialog, text="学号").pack(pady=5)
        fields['student_no'] = tk.Entry(dialog)
        fields['student_no'].pack()
        tk.Label(dialog, text="密码").pack(pady=5)
        fields['password'] = tk.Entry(dialog, show="*")
        fields['password'].pack()

        def submit():
            sid = fields['sid'].get().strip()
            sname = fields['sname'].get().strip()
            student_no = fields['student_no'].get().strip()
            pwd = fields['password'].get().strip()
            if not sid or not sname or not student_no or not pwd:
                messagebox.showerror("错误", "所有字段都必须填写")
                return
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO Student(sid, sname, student_no, password, arrears) VALUES (%s,%s,%s,%s,0)",
                               (sid, sname, student_no, pwd))
                conn.commit()
                messagebox.showinfo("成功", "添加成功")
                dialog.destroy()
                self.show_student_manage()
            except Error as e:
                conn.rollback()
                messagebox.showerror("错误", str(e))
            finally:
                cursor.close()
                conn.close()
        tk.Button(dialog, text="确定", command=submit).pack(pady=10)

    # ----------------------------- 借阅处理 ---------------------------------
    def show_borrow_handle(self):
        self.clear_frame()
        frame = self.main_frame
        tk.Label(frame, text="借阅处理", font=("Arial", 16)).pack(pady=10)

        tree = ttk.Treeview(frame, columns=("borrow_id","sid","sname","bid","bname","borrow_Date","due_Date"), show="headings", height=10)
        tree.heading("borrow_id", text="借阅ID")
        tree.heading("sid", text="学生号")
        tree.heading("sname", text="姓名")
        tree.heading("bid", text="图书号")
        tree.heading("bname", text="书名")
        tree.heading("borrow_Date", text="借书日期")
        tree.heading("due_Date", text="应还日期")
        tree.pack(pady=10, fill=tk.BOTH, expand=True)

        def refresh():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT br.borrow_id, s.sid, s.sname, b.bid, b.bname, br.borrow_Date, br.due_Date
                FROM Borrow br
                JOIN Student s ON br.student_ID = s.sid
                JOIN Book b ON br.book_ID = b.bid
                WHERE br.return_Date IS NULL
            """)
            rows = cursor.fetchall()
            tree.delete(*tree.get_children())
            for row in rows:
                tree.insert("", tk.END, values=row)
            cursor.close()
            conn.close()
        refresh()

        def return_book():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("警告", "请选择一条借阅记录")
                return
            borrow_id = tree.item(selected[0])['values'][0]
            if messagebox.askyesno("确认", "确认归还此书吗？"):
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.callproc('ReturnBook', (borrow_id,))
                    while cursor.nextset():   # 清空任何残留结果
                        pass
                    conn.commit()
                    messagebox.showinfo("成功", "还书成功")
                    refresh()
                except Error as e:
                    conn.rollback()
                    messagebox.showerror("错误", str(e))
                finally:
                    cursor.close()
                    conn.close()

        tk.Button(frame, text="归还所选图书", command=return_book).pack(pady=5)

        # 快速借书
        tk.Label(frame, text="快速借书", font=("Arial", 14)).pack(pady=10)
        sub_frame = tk.Frame(frame)
        sub_frame.pack(pady=5)
        tk.Label(sub_frame, text="学生号:").grid(row=0, column=0)
        sid_entry = tk.Entry(sub_frame, width=10)
        sid_entry.grid(row=0, column=1)
        tk.Label(sub_frame, text="图书号:").grid(row=0, column=2)
        bid_entry = tk.Entry(sub_frame, width=10)
        bid_entry.grid(row=0, column=3)
        def do_borrow():
            sid = sid_entry.get().strip()
            bid = bid_entry.get().strip()
            if not sid or not bid:
                messagebox.showerror("错误", "请填写学生号和图书号")
                return
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.callproc('BorrowBook', (sid, bid))
                for result in cursor.stored_results():
                    msg = result.fetchone()[0]
                    if "成功" in msg:
                        conn.commit()
                        messagebox.showinfo("成功", msg)
                        refresh()
                    else:
                        messagebox.showerror("失败", msg)
            except Error as e:
                conn.rollback()
                messagebox.showerror("错误", str(e))
            finally:
                cursor.close()
                conn.close()
        tk.Button(sub_frame, text="借书", command=do_borrow).grid(row=0, column=4, padx=5)

    # ----------------------------- 预约处理 ---------------------------------
    def show_reserve_handle(self):
        self.clear_frame()
        frame = self.main_frame
        tk.Label(frame, text="预约处理", font=("Arial", 16)).pack(pady=10)
        tree = ttk.Treeview(frame, columns=("reserve_id","bid","bname","sid","sname","reserve_Date"), show="headings", height=15)
        tree.heading("reserve_id", text="预约ID")
        tree.heading("bid", text="图书号")
        tree.heading("bname", text="书名")
        tree.heading("sid", text="学生号")
        tree.heading("sname", text="姓名")
        tree.heading("reserve_Date", text="预约日期")
        tree.pack(pady=10, fill=tk.BOTH, expand=True)

        def refresh():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.reserve_id, b.bid, b.bname, s.sid, s.sname, r.reserve_Date
                FROM Reserve r
                JOIN Book b ON r.book_ID = b.bid
                JOIN Student s ON r.student_ID = s.sid
                WHERE r.status = 0
                ORDER BY r.reserve_Date
            """)
            rows = cursor.fetchall()
            tree.delete(*tree.get_children())
            for row in rows:
                tree.insert("", tk.END, values=row)
            cursor.close()
            conn.close()
        refresh()

        def confirm_take():
            selected = tree.selection()
            if not selected:
                return
            values = tree.item(selected[0])['values']
            reserve_id, bid, bname, sid, sname, reserve_date = values
            if messagebox.askyesno("确认", f"为学生 {sname}({sid}) 办理图书 {bid} 的借阅吗？"):
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.callproc('BorrowBook', (sid, bid))
                    for result in cursor.stored_results():
                        msg = result.fetchone()[0]
                        if "成功" in msg:
                            conn.commit()
                            messagebox.showinfo("成功", "借阅成功，预约状态已更新为已取书")
                            refresh()
                        else:
                            messagebox.showerror("失败", msg)
                except Error as e:
                    conn.rollback()
                    messagebox.showerror("错误", str(e))
                finally:
                    cursor.close()
                    conn.close()

        tk.Button(frame, text="确认取书并借出", command=confirm_take).pack(pady=5)

    # ----------------------------- 逾期管理 ---------------------------------
    def show_overdue_manage(self):
        self.clear_frame()
        frame = self.main_frame
        tk.Label(frame, text="逾期记录管理", font=("Arial", 16)).pack(pady=10)
        tree = ttk.Treeview(frame, columns=("overdue_id","sid","sname","bid","bname","overdue_days","fine_amount","is_paid"), show="headings", height=15)
        tree.heading("overdue_id", text="逾期ID")
        tree.heading("sid", text="学生号")
        tree.heading("sname", text="姓名")
        tree.heading("bid", text="图书号")
        tree.heading("bname", text="书名")
        tree.heading("overdue_days", text="逾期天数")
        tree.heading("fine_amount", text="罚款金额")
        tree.heading("is_paid", text="是否缴纳")
        tree.pack(pady=10, fill=tk.BOTH, expand=True)

        def refresh():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.overdue_id, s.sid, s.sname, b.bid, b.bname, o.overdue_days, o.fine_amount,
                       CASE WHEN o.is_paid=1 THEN '已缴' ELSE '未缴' END
                FROM Overdue o
                JOIN Student s ON o.student_ID = s.sid
                JOIN Book b ON o.book_ID = b.bid
            """)
            rows = cursor.fetchall()
            tree.delete(*tree.get_children())
            for row in rows:
                tree.insert("", tk.END, values=row)
            cursor.close()
            conn.close()
        refresh()

        def delete_overdue():
            selected = tree.selection()
            if not selected:
                return
            overdue_id = tree.item(selected[0])['values'][0]
            if messagebox.askyesno("警告", "删除逾期记录会同时减免学生对应的欠费金额，确定删除吗？"):
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT student_ID, fine_amount FROM Overdue WHERE overdue_id=%s", (overdue_id,))
                    sid, fine = cursor.fetchone()
                    cursor.execute("DELETE FROM Overdue WHERE overdue_id=%s", (overdue_id,))
                    cursor.execute("UPDATE Student SET arrears = arrears - %s WHERE sid=%s", (fine, sid))
                    conn.commit()
                    messagebox.showinfo("成功", "已删除逾期记录")
                    refresh()
                except Exception as e:
                    conn.rollback()
                    messagebox.showerror("错误", str(e))
                finally:
                    cursor.close()
                    conn.close()

        tk.Button(frame, text="删除选中逾期记录", command=delete_overdue).pack(pady=5)

    # ----------------------------- 媒体管理（管理员）----------------------------------
    def upload_media(self):
        file_path = filedialog.askopenfilename(title="选择文件")
        if not file_path:
            return
        filename = os.path.basename(file_path)
        ext = filename.split('.')[-1].lower()
        upload_dir = "uploads"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        dest_path = os.path.join(upload_dir, f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}")
        shutil.copy2(file_path, dest_path)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Media(filename, filetype, filepath, uploader) VALUES (%s, %s, %s, %s)",
                       (filename, ext, dest_path, self.aid))
        conn.commit()
        cursor.close()
        conn.close()
        messagebox.showinfo("成功", f"文件 {filename} 上传成功")

    def show_media_gallery(self):
        self.clear_frame()
        frame = self.main_frame
        canvas = tk.Canvas(frame)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        conn = get_db_connection()
        cursor = conn.cursor()
        # 学生端查不到 uploader 字段，管理员端则需要查 uploader，这里统一简单查询
        cursor.execute("SELECT media_id, filename, filetype, filepath, upload_date FROM Media ORDER BY upload_date DESC")
        medias = cursor.fetchall()
        cursor.close()
        conn.close()

        for media in medias:
            media_id, filename, filetype, filepath, upload_date = media
            frm = tk.Frame(scrollable_frame, bd=1, relief=tk.RAISED)
            frm.pack(pady=5, padx=5, fill=tk.X)

            # 预览图片
            if filetype.lower() in ['jpg','jpeg','png','gif']:
                try:
                    img = Image.open(filepath)
                    img.thumbnail((80,80))
                    photo = ImageTk.PhotoImage(img)
                    lbl_img = tk.Label(frm, image=photo)
                    lbl_img.image = photo
                    lbl_img.pack(side=tk.LEFT, padx=5)
                except:
                    tk.Label(frm, text="[图片预览失败]").pack(side=tk.LEFT, padx=5)
            else:
                tk.Label(frm, text=f"[{filetype.upper()}文件]").pack(side=tk.LEFT, padx=5)

            info_text = f"{filename}\n上传时间: {upload_date}"
            tk.Label(frm, text=info_text, anchor="w").pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

            # 打开文件函数
            def open_file(path=filepath):
                if os.path.exists(path):
                    try:
                        if sys.platform == 'win32':
                            os.startfile(path)
                        elif sys.platform == 'darwin':
                            subprocess.run(['open', path])
                        else:
                            subprocess.run(['xdg-open', path])
                    except:
                        messagebox.showerror("错误", "无法打开文件")
                else:
                    messagebox.showerror("错误", "文件不存在")

            # 删除文件函数
            def delete_media(mid=media_id, path=filepath, fname=filename):
                if messagebox.askyesno("确认删除", f"确定删除文件 {fname} 吗？"):
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM Media WHERE media_id = %s", (mid,))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        if os.path.exists(path):
                            os.remove(path)
                        messagebox.showinfo("成功", "文件已删除")
                        self.show_media_gallery()  # 刷新
                    except Exception as e:
                        messagebox.showerror("错误", str(e))

            btn_frame = tk.Frame(frm)
            btn_frame.pack(side=tk.RIGHT, padx=5)
            tk.Button(btn_frame, text="打开", command=open_file).pack(side=tk.LEFT, padx=2)
            tk.Button(btn_frame, text="删除", command=delete_media).pack(side=tk.LEFT, padx=2)

    def logout(self):
        self.master.destroy()
        root = tk.Tk()
        LoginWindow(root)
        root.mainloop()

# ----------------------------- 程序入口 ---------------------------------
if __name__ == "__main__":
    init_media_table()
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    root = tk.Tk()
    LoginWindow(root)
    root.mainloop()