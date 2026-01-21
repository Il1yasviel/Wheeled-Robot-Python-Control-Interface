# -*- coding: utf-8 -*-
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
try:
    from ttkbootstrap.widgets.scrolled import ScrolledText 
except ImportError:
    from ttkbootstrap.scrolled import ScrolledText

from tkinter import Canvas
import serial
import serial.tools.list_ports
import math
import time
import threading
import datetime
import random

class CyberpunkCarControl:
    def __init__(self, root):
        self.root = root
        
        # --- 1. 移除系统原生标题栏 ---
        self.root.overrideredirect(True) 
        
                # 【新增】设置窗口一直置顶
        self.root.attributes('-topmost', True)

        # --- 视觉配置 ---
        self.color_bg = "#050505"       
        self.color_grid = "#003333"     
        self.color_main = "#00ffcc"     
        self.color_accent = "#FF2D2D"   
        self.color_eva_red = "#FF2D2D" 
        self.color_warning_bg = "#1A0505" 
        self.color_dim = "#0F2A2A"      
        
        # --- 窗口初始化 ---
        self.width = 1000
        self.height = 1030
        self.center_window(self.width, self.height)
        self.root.configure(bg="black")
        
        # --- 串口变量 ---
        self.ser = None
        self.is_connected = False
        
        # --- 摇杆参数 ---
        self.canvas_size = 500 
        self.center_x = self.canvas_size // 2
        self.center_y = self.canvas_size // 2
        self.joystick_radius = 190 
        self.knob_radius = 35
        self.max_val = 100
        
        # --- 键盘控制 ---
        self.keys = {'w': False, 's': False, 'a': False, 'd': False}
        
        # --- 【核心修改】发送逻辑变量 ---
        self.last_send_time = 0
        
        # 1. 发送间隔改为 150ms (0.15) - 极低速稳定模式
        self.send_interval = 0.15
        
        self.last_sent_m = None
        self.last_sent_t = None

        # --- 构建界面 ---
        self.setup_custom_title_bar() 
        self.setup_ui()
        self.setup_resize_grip() 
        self.bind_keyboard_events() 

        self.append_log("[SYS] SYSTEM INITIALIZED...")
        self.append_log("[SYS] WAITING FOR CONNECTION...")

    def center_window(self, w, h):
        """让窗口在屏幕居中"""
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def setup_custom_title_bar(self):
        """创建自定义的黑色标题栏"""
        self.title_bar = tk.Frame(self.root, bg="black", relief="flat", bd=0)
        self.title_bar.pack(fill="x", side="top")

        title_label = tk.Label(self.title_bar, text="NEXUS-7 ROBOTIC CONTROLLER", 
                               bg="black", fg=self.color_eva_red, 
                               font=("Impact", 14))
        title_label.pack(side="left", padx=10, pady=5)

        close_btn = tk.Button(self.title_bar, text=" [ X ] ", command=self.close_app,
                              bg="black", fg=self.color_eva_red, 
                              font=("Consolas", 12, "bold"), 
                              bd=0, activebackground=self.color_eva_red, activeforeground="black")
        close_btn.pack(side="right", padx=5, pady=5)

        self.title_bar.bind("<Button-1>", self.get_pos)
        self.title_bar.bind("<B1-Motion>", self.move_window)
        title_label.bind("<Button-1>", self.get_pos)
        title_label.bind("<B1-Motion>", self.move_window)

    def setup_resize_grip(self):
        """添加右下角调整大小的手柄"""
        self.grip = ttk.Sizegrip(self.root, bootstyle="secondary")
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<B1-Motion>", self.on_resize)

    def on_resize(self, event):
        x1 = self.root.winfo_pointerx()
        y1 = self.root.winfo_pointery()
        x0 = self.root.winfo_rootx()
        y0 = self.root.winfo_rooty()
        new_width = x1 - x0
        new_height = y1 - y0
        if new_width < 600: new_width = 600
        if new_height < 600: new_height = 600
        self.root.geometry(f"{new_width}x{new_height}")

    def get_pos(self, event):
        self.x_click = event.x
        self.y_click = event.y

    def move_window(self, event):
        delta_x = event.x - self.x_click
        delta_y = event.y - self.y_click
        new_x = self.root.winfo_x() + delta_x
        new_y = self.root.winfo_y() + delta_y
        self.root.geometry(f"+{new_x}+{new_y}")

    def close_app(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.destroy()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)

        # 1. 顶部连接模块
        status_frame = ttk.Frame(main_frame, padding=(10, 5))
        status_frame.pack(fill="x")
        
        header_frame = ttk.Frame(status_frame)
        header_frame.pack(fill="x")
        
        ttk.Label(header_frame, text="/// SYSTEM LINK // OMEGA LEVEL", font=("Impact", 16), foreground=self.color_main).pack(side="left")
        
        conn_frame = ttk.Frame(header_frame)
        conn_frame.pack(side="right")
        
        self.port_combobox = ttk.Combobox(conn_frame, width=12, font=("Consolas", 10))
        self.port_combobox.pack(side="left", padx=5)
        
        ttk.Button(conn_frame, text="SCAN", command=self.refresh_ports, bootstyle="outline-info", width=6).pack(side="left", padx=2)
        self.btn_connect = ttk.Button(conn_frame, text="CONNECT", command=self.toggle_connect, bootstyle="success-outline", width=12)
        self.btn_connect.pack(side="left", padx=2)
        
        self.refresh_ports()

        # 2. EVA 风格警告带
        warning_height = 130 
        stripe_h = 25
        self.warn_canvas = Canvas(main_frame, height=warning_height, bg=self.color_bg, highlightthickness=0)
        self.warn_canvas.pack(fill="x", pady=0)
        
        self.draw_warning_stripes(self.warn_canvas, 0, 1000, stripe_h)             
        self.draw_warning_stripes(self.warn_canvas, warning_height - stripe_h, 1000, stripe_h) 
        
        self.warn_canvas.create_text(500, warning_height/2, text="E M E R G E N C Y   O V E R R I D E", 
                                     font=("Impact", 42), fill=self.color_eva_red)

        # 3. 中间控制区域
        middle_container = ttk.Frame(main_frame)
        middle_container.pack(fill="x", expand=False, pady=10)

        self.left_canvas = Canvas(middle_container, width=200, height=self.canvas_size, 
                                  bg=self.color_bg, highlightthickness=0)
        self.left_canvas.pack(side="left", fill="both", expand=True)
        self.draw_side_decor(self.left_canvas, "left")

        self.canvas = Canvas(middle_container, width=self.canvas_size, height=self.canvas_size, 
                             bg="#000000", highlightthickness=2, highlightbackground=self.color_grid)
        self.canvas.pack(side="left", padx=0) 

        self.right_canvas = Canvas(middle_container, width=200, height=self.canvas_size, 
                                   bg=self.color_bg, highlightthickness=0)
        self.right_canvas.pack(side="left", fill="both", expand=True)
        self.draw_side_decor(self.right_canvas, "right")

        self.draw_radar_grid()

        self.knob_glow = self.canvas.create_oval(0,0,0,0, fill=self.color_accent, outline="", stipple="gray50") 
        self.knob = self.canvas.create_oval(0,0,0,0, fill="black", outline=self.color_accent, width=3)
        self.knob_center = self.canvas.create_oval(0,0,0,0, fill="white", outline="")
        self.update_joystick_pos(self.center_x, self.center_y)

        self.canvas.tag_bind(self.knob, "<B1-Motion>", self.on_drag)
        self.canvas.tag_bind(self.knob, "<ButtonRelease-1>", self.on_release)
        self.canvas.tag_bind(self.knob_center, "<B1-Motion>", self.on_drag)
        self.canvas.tag_bind(self.knob_center, "<ButtonRelease-1>", self.on_release)

        # 4. 数据仪表
        dash_frame = tk.Frame(main_frame, bg="black", pady=10)
        dash_frame.pack(fill="x")
        
        f1 = tk.Frame(dash_frame, bg="black")
        f1.pack(side="left", fill="x", expand=True, padx=5)
        
        tk.Label(f1, text="VELOCITY // M/S", font=("Impact", 14), fg="gray", bg="black").pack()
        self.lbl_speed = tk.Label(f1, text="+000", font=("Orbitron", 32, "bold"), fg=self.color_eva_red, bg="black")
        self.lbl_speed.pack()

        f2 = tk.Frame(dash_frame, bg="black")
        f2.pack(side="left", fill="x", expand=True, padx=5)
        
        tk.Label(f2, text="AZIMUTH // DEG", font=("Impact", 14), fg="gray", bg="black").pack()
        self.lbl_turn = tk.Label(f2, text="+000", font=("Orbitron", 32, "bold"), fg=self.color_eva_red, bg="black")
        self.lbl_turn.pack()

        # 5. 日志区域
        log_container = ttk.Frame(main_frame, padding=(10, 10))
        log_container.pack(fill="both", expand=True)

        ttk.Label(log_container, text="NEURAL LINK LOG // RX_DATA_STREAM", font=("Consolas", 9), foreground=self.color_main).pack(anchor="w")
        
        self.console_text = ScrolledText(log_container, font=("Consolas", 10), bootstyle="secondary")
        self.console_text.pack(fill="both", expand=True)
        self.console_text.text.configure(bg="#020a0a", fg="#00ff00", insertbackground="white", selectbackground=self.color_accent)

        self.read_thread = threading.Thread(target=self.read_serial_loop)
        self.read_thread.daemon = True
        self.read_thread.start()

    def draw_radar_grid(self):
        step = 40
        for i in range(0, self.canvas_size+1, step):
            self.canvas.create_line(i, 0, i, self.canvas_size, fill="#081818")
            self.canvas.create_line(0, i, self.canvas_size, i, fill="#081818")
        
        self.canvas.create_line(self.center_x, 0, self.center_x, self.canvas_size, fill=self.color_grid, width=2)
        self.canvas.create_line(0, self.center_y, self.canvas_size, self.center_y, fill=self.color_grid, width=2)

        for r in [70, 140, 210, 240]:
            width = 1 if r != 210 else 3
            outline = self.color_dim if r != 210 else self.color_main
            self.canvas.create_oval(self.center_x-r, self.center_y-r, self.center_x+r, self.center_y+r, 
                                    outline=outline, width=width)
            
        self.canvas.create_text(self.center_x, 40, text="/// MANUAL OVERRIDE ///", fill=self.color_accent, font=("Impact", 12))
        self.canvas.create_text(self.center_x, self.canvas_size-40, text="LOCK_TARGET: NULL", fill=self.color_grid, font=("Consolas", 10))

    def draw_warning_stripes(self, canvas, y_pos, width, height):
        canvas.create_rectangle(0, y_pos, width, y_pos+height, fill=self.color_warning_bg, width=0)
        stripe_width = 30
        gap = 50
        for x in range(-50, 1200, gap):
            points = [x, y_pos + height, x + stripe_width, y_pos + height, x + stripe_width + 20, y_pos, x + 20, y_pos]
            canvas.create_polygon(points, fill=self.color_eva_red)

    def draw_side_decor(self, canvas, side):
        w = 250 
        h = self.canvas_size
        for i in range(0, h, 20):
            canvas.create_line(0, i, w, i, fill="#050a0a")

        if side == "left":
            canvas.create_rectangle(150, 50, 170, h-50, outline=self.color_grid, width=2)
            for i in range(60, h-60, 10):
                color = self.color_main if i > h/2 else self.color_eva_red
                if i % 30 == 0:
                    canvas.create_rectangle(154, i, 166, i+6, fill=color, outline="")
            x_text = 80
            y_text = 100
            canvas.create_text(x_text, 60, text="SYS.KERNEL.DUMP", fill="gray", font=("Consolas", 8), anchor="e")
            for _ in range(15):
                hex_str = ' '.join([f"{random.randint(0,255):02X}" for _ in range(3)])
                canvas.create_text(x_text, y_text, text=hex_str, fill=self.color_dim, font=("Consolas", 9), anchor="e")
                y_text += 20
            canvas.create_rectangle(20, h-150, 100, h-50, outline=self.color_accent, width=2)
            canvas.create_text(60, h-100, text="CAUTION\nHIGH VOLT", fill=self.color_accent, font=("Impact", 10), justify="center")

        elif side == "right":
            self.draw_vertical_stripes(canvas, 30, 0, h, 40)
            x_base = 100
            y_base = 80
            statuses = ["GYRO: STABLE", "TEMP: 450K", "FUEL: 98%", "AMMO: NULL", "LINK: OK", "PING: 12ms"]
            for s in statuses:
                canvas.create_rectangle(x_base, y_base, x_base+5, y_base+5, fill=self.color_main)
                canvas.create_text(x_base+15, y_base+3, text=s, fill=self.color_main, font=("Consolas", 10), anchor="w")
                y_base += 30
            canvas.create_rectangle(90, h-180, 180, h-80, fill=self.color_warning_bg, outline=self.color_eva_red)
            canvas.create_text(135, h-130, text="NO\nSIGNAL", fill=self.color_eva_red, font=("Impact", 14), justify="center")

    def draw_vertical_stripes(self, canvas, x_pos, y_start, y_end, width):
        gap = 40
        for y in range(y_start, y_end, gap):
            points = [x_pos, y, x_pos + width, y, x_pos + width, y + 20, x_pos, y + 20]
            canvas.create_polygon(points, fill="#111", outline=self.color_grid)
            canvas.create_line(x_pos, y, x_pos+width, y+20, fill=self.color_grid)

    def bind_keyboard_events(self):
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)

    def on_key_press(self, event):
        key = event.keysym.lower()
        if key in self.keys:
            if not self.keys[key]: 
                self.keys[key] = True
                self.update_joystick_from_keys()

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in self.keys:
            self.keys[key] = False
            self.update_joystick_from_keys()

    def update_joystick_from_keys(self):
        target_x = 0
        target_y = 0
        
        # --- 修改开始 ---
        # 原来的代码是: offset = self.joystick_radius * 0.8
        
        # 这里我们将速度(W/S)和转向(A/D)分开设置
        # 0.3 代表 30% (即速度 30)
        # 0.8 代表 80% (即转向 80，建议转向保持大一点，否则转弯半径会很大)
        
        offset_speed = self.joystick_radius * 0.1  # <--- W/S 键力度改为 0.3
        offset_turn = self.joystick_radius * 0.8   # <--- A/D 键力度保持 0.8 (可按需修改)

        if self.keys['w']: target_y -= offset_speed 
        if self.keys['s']: target_y += offset_speed
        if self.keys['a']: target_x -= offset_turn 
        if self.keys['d']: target_x += offset_turn
        # --- 修改结束 ---

        abs_x = self.center_x + target_x
        abs_y = self.center_y + target_y

        self.update_joystick_pos(abs_x, abs_y)
        
        # 计算最终数值
        speed_val = int(-target_y / self.joystick_radius * self.max_val)
        turn_val = int(-target_x / self.joystick_radius * self.max_val) 
        
        self.update_values(speed_val, turn_val, force=True)

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_combobox['values'] = port_list
        if port_list: self.port_combobox.current(0)

    def toggle_connect(self):
        if not self.is_connected:
            try:
                port = self.port_combobox.get()
                self.ser = serial.Serial(port, 115200, timeout=0.1)
                self.is_connected = True
                self.btn_connect.config(text="DISCONNECT", bootstyle="danger")
                self.append_log(f"[SYS] >> LINK ESTABLISHED: {port}") 
                self.root.focus_set() 
                self.last_sent_m = None
                self.last_sent_t = None
            except Exception as e:
                self.append_log(f"[SYS] !! ERROR: {e}")
        else:
            self.is_connected = False
            if self.ser: self.ser.close()
            self.btn_connect.config(text="CONNECT", bootstyle="success-outline")
            self.append_log("[SYS] >> LINK TERMINATED")

    def on_drag(self, event):
        dx = event.x - self.center_x
        dy = event.y - self.center_y
        distance = math.sqrt(dx*dx + dy*dy)

        if distance > self.joystick_radius:
            ratio = self.joystick_radius / distance
            dx *= ratio
            dy *= ratio

        self.update_joystick_pos(self.center_x + dx, self.center_y + dy)
        speed_val = int(-dy / self.joystick_radius * self.max_val)
        turn_val = int(-dx / self.joystick_radius * self.max_val)
        self.update_values(speed_val, turn_val)

    def on_release(self, event):
        self.update_joystick_pos(self.center_x, self.center_y)
        self.update_values(0, 0, force=True) 
        if self.is_connected:
            self.send_command("S") 

    def update_joystick_pos(self, x, y):
        r = self.knob_radius
        self.canvas.coords(self.knob, x-r, y-r, x+r, y+r)
        gr = r + 8 
        self.canvas.coords(self.knob_glow, x-gr, y-gr, x+gr, y+gr)
        self.canvas.coords(self.knob_center, x-3, y-3, x+3, y+3)

    # --- 关键修改：150ms 极低速稳定模式 ---
    def update_values(self, m, t, force=False):
        if self.lbl_speed: self.lbl_speed.config(text=f"{m:+04d}")
        if self.lbl_turn: self.lbl_turn.config(text=f"{t:+04d}")
        
        current_time = time.time()
        
        if self.is_connected and self.ser and self.ser.is_open:
            
            # 1. 检查时间间隔 (150ms)
            if force or (current_time - self.last_send_time > self.send_interval):
                try:
                    # --- A. 发送速度 M ---
                    if force or (m != self.last_sent_m):
                        cmd_m = f"M{m}\r\n"
                        self.ser.write(cmd_m.encode('utf-8'))
                        self.last_sent_m = m
                        
                        # 【核心修改】增加等待时间到 80ms
                        # 留出充足时间防止单片机阻塞
                        time.sleep(0.08) 

                    # --- B. 发送转向 T ---
                    if force or (t != self.last_sent_t):
                        cmd_t = f"T{t}\r\n"
                        self.ser.write(cmd_t.encode('utf-8'))
                        self.last_sent_t = t

                    # 更新时间戳
                    self.last_send_time = time.time()

                except Exception as e:
                    self.append_log(f"[TX] !! Send Error: {e}")

    def send_command(self, cmd_str):
        if self.ser and self.ser.is_open:
            try:
                data = f"{cmd_str}\r\n".encode('utf-8')
                self.ser.write(data)
            except Exception as e:
                self.append_log(f"[TX] !! Send Error: {e}")

    def read_serial_loop(self):
        while True:
            if self.is_connected and self.ser:
                try:
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            self.root.after(0, self.append_log, f"[RX] << {line}")
                except Exception:
                    pass
            time.sleep(0.01)

    def append_log(self, text):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {text}\n"
        self.console_text.insert(tk.END, full_msg)
        self.console_text.see(tk.END)

if __name__ == "__main__":
    root = ttk.Window(themename="cyborg")
    app = CyberpunkCarControl(root)
    root.mainloop()