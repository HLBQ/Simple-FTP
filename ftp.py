import os
import tkinter as tk
from tkinter import ttk, filedialog
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from pathlib import Path
import threading
import socket
import sys
import ctypes

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path

class MiniFTPTool:
    def __init__(self, root):
        self.root = root
        self.root.title("FTP工具")
        self.root.geometry("380x160")
        self.root.resizable(False, False)
        try:
            icon_path = get_resource_path("icon.png")
            if os.path.exists(icon_path):
                icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon)
                self.root.icon_image = icon  
        except Exception as e:
            pass

        self.server = None
        self.thread = None
        self.is_running = False
        
        self.local_ip = self.get_local_ip()

        frame1 = tk.Frame(root)
        frame1.pack(pady=5, fill=tk.X, padx=10)

        tk.Label(frame1, text="IP:").grid(row=0, column=0, padx=5)
        self.ip_label = ttk.Label(frame1, text=self.local_ip, width=15)
        self.ip_label.grid(row=0, column=1, padx=5)

        tk.Label(frame1, text="端口:").grid(row=0, column=2, padx=5)
        self.port_entry = ttk.Entry(frame1, width=8)
        self.port_entry.grid(row=0, column=3, padx=5)
        self.port_entry.insert(0, "21")

        self.port_entry.bind("<KeyRelease>", self.auto_restart)

        frame2 = tk.Frame(root)
        frame2.pack(pady=5, fill=tk.X, padx=10)

        tk.Label(frame2, text="共享路径:").pack(side=tk.LEFT, padx=5)
        self.path_entry = ttk.Entry(frame2)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.path_entry.insert(0, os.getcwd())

        ttk.Button(frame2, text="浏览", command=self.select_path).pack(side=tk.LEFT, padx=5)
        self.path_entry.bind("<KeyRelease>", self.auto_restart)

        frame3 = tk.Frame(root)
        frame3.pack(pady=5, padx=10)

        self.read_var = tk.BooleanVar(value=True)
        self.write_var = tk.BooleanVar(value=False)
        self.del_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(frame3, text="读取", variable=self.read_var).grid(row=0, column=0, padx=15)
        ttk.Checkbutton(frame3, text="写入", variable=self.write_var).grid(row=0, column=1, padx=15)
        ttk.Checkbutton(frame3, text="删除", variable=self.del_var).grid(row=0, column=2, padx=15)

        self.read_var.trace("w", self.auto_restart)
        self.write_var.trace("w", self.auto_restart)
        self.del_var.trace("w", self.auto_restart)

        frame4 = tk.Frame(root)
        frame4.pack(pady=8)

        self.toggle_btn = ttk.Button(frame4, text="启动服务", command=self.toggle_server)
        self.toggle_btn.pack()

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            for addr in socket.gethostbyname_ex(socket.gethostname())[2]:
                if not addr.startswith("127."):
                    return addr
            return "127.0.0.1"

    def select_path(self):
        path = filedialog.askdirectory()
        if path:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)
            self.auto_restart()

    def get_permission(self):
        perm = "e" 
        if self.read_var.get():
            perm += "lr"  
        if self.write_var.get():
            perm += "lw" 
        if self.del_var.get():
            perm += "d"   
        return perm

    def log_event(self, msg):
        print(msg)

    def toggle_server(self):
        if not self.is_running:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        if self.is_running:
            return
        ip = self.local_ip  
        try:
            port = int(self.port_entry.get().strip())
            if port < 1 or port > 65535:
                self.log_event("端口号必须在1-65535之间")
                return
        except ValueError:
            self.log_event("端口号必须是数字")
            return
        
        path = self.path_entry.get().strip()
        if not os.path.isdir(path):
            self.log_event(f"共享路径无效: {path}")
            return
        
        perm = self.get_permission()

        try:
            authorizer = DummyAuthorizer()
            authorizer.add_anonymous(path, perm=perm)

            class CustomFTPHandler(FTPHandler):
                log_prefix = '[%(remote_ip)s] '
                passive_ports = range(50000, 50100)
                allow_unknown_ip_modes = True

                def on_file_received(self, file_path):
                    ip = self.remote_ip
                    name = os.path.basename(file_path)
                    try:
                        size = os.path.getsize(file_path)
                        self.log(f"上传文件: {name} | 大小: {size} 字节 | 路径: {file_path}")
                    except Exception as e:
                        self.log(f"上传文件: {name} | 获取大小失败: {e}")

                def on_file_sent(self, file_path):
                    ip = self.remote_ip
                    name = os.path.basename(file_path)
                    try:
                        size = os.path.getsize(file_path)
                        self.log(f"下载文件: {name} | 大小: {size} 字节 | 路径: {file_path}")
                    except Exception as e:
                        self.log(f"下载文件: {name} | 获取大小失败: {e}")

                def on_file_deleted(self, file_path):
                    ip = self.remote_ip
                    self.log(f"删除文件: {file_path}")

            CustomFTPHandler.authorizer = authorizer

            self.server = FTPServer((ip, port), CustomFTPHandler)
            self.server.allow_reuse_address = True

            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()

            self.is_running = True
            self.toggle_btn.config(text="停止服务")
            self.log_event(f"FTP服务启动成功 | IP: {ip} | 端口: {port} | 共享路径: {path} | 权限: {perm}")
            self.log_event(f"被动模式端口范围: 50000-50100（请确保防火墙已开放）")
            
        except socket.error as e:
            self.log_event(f"启动失败: 端口{port}可能被占用 - {e}")
        except Exception as e:
            self.log_event(f"启动失败: {str(e)}")
            self.is_running = False

    def stop_server(self):
        if not self.is_running or self.server is None:
            return
        
        try:
            self.server.close_all()
            if self.thread is not None:
                self.thread.join(timeout=1)
            
            self.server = None
            self.thread = None
            self.is_running = False
            self.toggle_btn.config(text="启动服务")
            self.log_event("FTP服务已正常停止")
            
        except Exception as e:
            self.log_event(f"停止服务时出现异常: {str(e)}")
            self.server = None
            self.thread = None
            self.is_running = False
            self.toggle_btn.config(text="启动服务")

    def auto_restart(self, *args):
        if self.is_running:
            self.log_event("配置已修改，正在重启FTP服务...")
            self.stop_server()
            self.root.after(500, self.start_server)

if __name__ == "__main__":
    if sys.platform == "win32" and not ctypes.windll.shell32.IsUserAnAdmin():
        print("提示：建议以管理员权限运行，避免权限不足问题！")
    
    root = tk.Tk()
    app = MiniFTPTool(root)
    root.mainloop()