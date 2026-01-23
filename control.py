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
        self.root.attributes('-topmost', True)

        # --- 视觉配置 ---
        self.color_bg = "#050505"       
        self.color_grid = "#003333"     
        self.color_main = "#00ffcc"     
        self.color_accent = "#FF2D2D"   
        self.color_eva_red = "#FF2D2D" 
        self.color_warning_bg = "#1A0505" 
        self.color_dim = "#0F2A2A"      
        self.color_sec_joy = "#FFD700"  # 第二摇杆高亮色（金色）
        self.color_alert = "#FFD700"    # 警告黄
        
        # --- 窗口初始化 ---
        self.width = 1300 
        self.height = 1000
        self.center_window(self.width, self.height)
        self.root.configure(bg="black")
        
        # --- 串口变量 ---
        self.ser = None
        self.is_connected = False
        
        # --- 摇杆1 (移动 M/T) 参数 ---
        self.joy1_size = 350 
        self.joy1_center = self.joy1_size // 2
        self.joy1_radius = 130 
        self.knob_radius = 30
        self.max_val_move = 100
        
        # --- 摇杆2 (姿态 R/H) 参数 ---
        self.joy2_size = 350
        self.joy2_center = self.joy2_size // 2
        self.joy2_radius = 130
        
        # R (左右) 参数
        self.val_r = 0.0
        self.default_r = 0.0
        self.min_r = -30.0
        self.max_r = 30.0
        self.step_r = 60.0 / 20.0  # 3.0
        
        # H (上下) 参数
        self.val_h = 110.0
        self.default_h = 110.0
        self.min_h = 83.0
        self.max_h = 137.0
        self.step_h = (137.0 - 83.0) / 20.0 # 2.7

        # --- 键盘控制状态 ---
        self.keys_move = {'w': False, 's': False, 'a': False, 'd': False}
        self.keys_pose = {'Up': False, 'Down': False, 'Left': False, 'Right': False}
        
        # 长按/自动回中 计时器
        self.pose_key_timers = {} 
        self.last_pose_action_time = time.time()

        # --- 发送逻辑变量 ---
        self.last_send_time = 0
        self.send_interval = 0.15 
        self.last_sent_m = None
        self.last_sent_t = None

        # --- 构建界面 ---
        self.setup_custom_title_bar() 
        self.setup_ui()
        self.setup_resize_grip() 
        self.bind_keyboard_events() 

        # --- 启动逻辑 ---
        self.append_log("[SYS] SYSTEM INITIALIZED...")
        self.append_log("[SYS] WAITING FOR CONNECTION...")
        
        # 启动按键扫描循环 (处理长按)
        self.check_pose_keys_loop()
        # 启动自动回中循环
        self.auto_return_loop()

    def center_window(self, w, h):
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def setup_custom_title_bar(self):
        self.title_bar = tk.Frame(self.root, bg="black", relief="flat", bd=0)
        self.title_bar.pack(fill="x", side="top")
        title_label = tk.Label(self.title_bar, text="NEXUS-7 DUAL LINK CONTROLLER", 
                               bg="black", fg=self.color_eva_red, font=("Impact", 14))
        title_label.pack(side="left", padx=10, pady=5)
        close_btn = tk.Button(self.title_bar, text=" [ X ] ", command=self.close_app,
                              bg="black", fg=self.color_eva_red, font=("Consolas", 12, "bold"), 
                              bd=0, activebackground=self.color_eva_red, activeforeground="black")
        close_btn.pack(side="right", padx=5, pady=5)
        self.title_bar.bind("<Button-1>", self.get_pos)
        self.title_bar.bind("<B1-Motion>", self.move_window)
        title_label.bind("<Button-1>", self.get_pos)
        title_label.bind("<B1-Motion>", self.move_window)

    def setup_resize_grip(self):
        self.grip = ttk.Sizegrip(self.root, bootstyle="secondary")
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<B1-Motion>", self.on_resize)

    def on_resize(self, event):
        x1 = self.root.winfo_pointerx()
        y1 = self.root.winfo_pointery()
        x0 = self.root.winfo_rootx()
        y0 = self.root.winfo_rooty()
        self.root.geometry(f"{x1-x0}x{y1-y0}")

    def get_pos(self, event):
        self.x_click = event.x
        self.y_click = event.y

    def move_window(self, event):
        self.root.geometry(f"+{event.x_root - self.x_click}+{event.y_root - self.y_click}")

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

        # 2. 警告带
        warning_height = 80 
        stripe_h = 15
        self.warn_canvas = Canvas(main_frame, height=warning_height, bg=self.color_bg, highlightthickness=0)
        self.warn_canvas.pack(fill="x", pady=0)
        self.draw_warning_stripes(self.warn_canvas, 0, 2000, stripe_h)             
        self.draw_warning_stripes(self.warn_canvas, warning_height - stripe_h, 2000, stripe_h) 
        self.warn_canvas.create_text(650, warning_height/2, text="M A N U A L   O V E R R I D E", 
                                     font=("Impact", 32), fill=self.color_eva_red)

        # 3. 中间控制区域
        middle_container = ttk.Frame(main_frame)
        middle_container.pack(fill="x", expand=False, pady=10)

        # [A] 左侧装饰面板
        self.decor_l = Canvas(middle_container, width=160, height=self.joy1_size, bg=self.color_bg, highlightthickness=0)
        self.decor_l.pack(side="left", fill="y", padx=0)
        self.draw_side_decor(self.decor_l, "left")

        # [B] 摇杆 1 (WASD)
        self.canvas1 = Canvas(middle_container, width=self.joy1_size, height=self.joy1_size, 
                             bg="#000000", highlightthickness=2, highlightbackground=self.color_grid)
        self.canvas1.pack(side="left", padx=5)
        self.draw_radar_grid(self.canvas1, self.joy1_size, self.joy1_center, "LOCOMOTION")
        self.knob1_glow = self.canvas1.create_oval(0,0,0,0, fill=self.color_accent, outline="", stipple="gray50") 
        self.knob1 = self.canvas1.create_oval(0,0,0,0, fill="black", outline=self.color_accent, width=3)
        self.knob1_center = self.canvas1.create_oval(0,0,0,0, fill="white", outline="")
        self.update_joy1_ui(self.joy1_center, self.joy1_center)
        
        self.canvas1.tag_bind(self.knob1, "<B1-Motion>", self.on_drag_joy1)
        self.canvas1.tag_bind(self.knob1, "<ButtonRelease-1>", self.on_release_joy1)
        self.canvas1.tag_bind(self.knob1_center, "<B1-Motion>", self.on_drag_joy1)
        self.canvas1.tag_bind(self.knob1_center, "<ButtonRelease-1>", self.on_release_joy1)

        # [C] 中间数据仪表
        data_panel = tk.Frame(middle_container, bg="black", width=120)
        data_panel.pack(side="left", fill="y", padx=5)
        
        tk.Label(data_panel, text="SPD (M)", fg="gray", bg="black", font=("Consolas", 8)).pack(pady=(40,0))
        self.lbl_speed = tk.Label(data_panel, text="+000", fg=self.color_main, bg="black", font=("Orbitron", 14))
        self.lbl_speed.pack()
        tk.Label(data_panel, text="TRN (T)", fg="gray", bg="black", font=("Consolas", 8)).pack(pady=(10,0))
        self.lbl_turn = tk.Label(data_panel, text="+000", fg=self.color_main, bg="black", font=("Orbitron", 14))
        self.lbl_turn.pack()
        
        tk.Frame(data_panel, height=2, bg=self.color_grid).pack(fill="x", pady=20)
        
        tk.Label(data_panel, text="ROLL (R)", fg="gray", bg="black", font=("Consolas", 8)).pack()
        self.lbl_r = tk.Label(data_panel, text="0.0", fg=self.color_sec_joy, bg="black", font=("Orbitron", 14))
        self.lbl_r.pack()
        tk.Label(data_panel, text="HGT (H)", fg="gray", bg="black", font=("Consolas", 8)).pack(pady=(10,0))
        self.lbl_h = tk.Label(data_panel, text="110.0", fg=self.color_sec_joy, bg="black", font=("Orbitron", 14))
        self.lbl_h.pack()

        # [D] 摇杆 2 (箭头 - R/H)
        self.canvas2 = Canvas(middle_container, width=self.joy2_size, height=self.joy2_size, 
                             bg="#000000", highlightthickness=2, highlightbackground=self.color_grid)
        self.canvas2.pack(side="left", padx=5)
        self.draw_radar_grid(self.canvas2, self.joy2_size, self.joy2_center, "ATTITUDE CTL")
        
        self.knob2_glow = self.canvas2.create_oval(0,0,0,0, fill=self.color_sec_joy, outline="", stipple="gray50") 
        self.knob2 = self.canvas2.create_oval(0,0,0,0, fill="black", outline=self.color_sec_joy, width=3)
        self.knob2_center = self.canvas2.create_oval(0,0,0,0, fill="white", outline="")
        self.update_joy2_ui_from_val()
        
        self.canvas2.tag_bind(self.knob2, "<B1-Motion>", self.on_drag_joy2)
        self.canvas2.tag_bind(self.knob2, "<ButtonRelease-1>", self.on_release_joy2) 
        self.canvas2.tag_bind(self.knob2_center, "<B1-Motion>", self.on_drag_joy2)
        self.canvas2.tag_bind(self.knob2_center, "<ButtonRelease-1>", self.on_release_joy2)
        self.canvas2.bind("<ButtonRelease-1>", self.on_release_joy2)

        # [E] 右侧装饰面板 (重新设计避免遮挡)
        self.decor_r = Canvas(middle_container, width=160, height=self.joy1_size, bg=self.color_bg, highlightthickness=0)
        self.decor_r.pack(side="left", fill="y", padx=0)
        self.draw_side_decor(self.decor_r, "right")

        # 4. 日志区域
        log_container = ttk.Frame(main_frame, padding=(10, 10))
        log_container.pack(fill="both", expand=True)
        ttk.Label(log_container, text="NEURAL LINK LOG // RX_DATA_STREAM", font=("Consolas", 9), foreground=self.color_main).pack(anchor="w")
        self.console_text = ScrolledText(log_container, font=("Consolas", 10), bootstyle="secondary", height=5)
        self.console_text.pack(fill="both", expand=True)
        self.console_text.text.configure(bg="#020a0a", fg="#00ff00", insertbackground="white")

        self.read_thread = threading.Thread(target=self.read_serial_loop)
        self.read_thread.daemon = True
        self.read_thread.start()

    # --- 绘图逻辑 ---
    def draw_warning_stripes(self, canvas, y_pos, width, height):
        canvas.create_rectangle(0, y_pos, width, y_pos+height, fill=self.color_warning_bg, width=0)
        stripe_width = 30
        gap = 50
        for x in range(-50, 2000, gap):
            points = [x, y_pos + height, x + stripe_width, y_pos + height, x + stripe_width + 20, y_pos, x + 20, y_pos]
            canvas.create_polygon(points, fill=self.color_eva_red)

    def draw_side_decor(self, canvas, side):
        w = 160 
        h = self.joy1_size
        
        # 背景线
        for i in range(0, h, 20):
            canvas.create_line(0, i, w, i, fill="#050a0a")

        if side == "left":
            canvas.create_rectangle(140, 50, 150, h-50, outline=self.color_grid, width=2)
            for i in range(60, h-60, 10):
                color = self.color_main if i > h/2 else self.color_eva_red
                if i % 30 == 0:
                    canvas.create_rectangle(142, i, 148, i+6, fill=color, outline="")
            
            x_text = 120
            y_text = 100
            canvas.create_text(x_text, 60, text="SYS.KERNEL.DUMP", fill="gray", font=("Consolas", 8), anchor="e")
            for _ in range(12):
                hex_str = ' '.join([f"{random.randint(0,255):02X}" for _ in range(3)])
                canvas.create_text(x_text, y_text, text=hex_str, fill=self.color_dim, font=("Consolas", 9), anchor="e")
                y_text += 20
            
            canvas.create_rectangle(10, h-150, 90, h-50, outline=self.color_accent, width=2)
            canvas.create_text(50, h-100, text="CAUTION\nHIGH VOLT", fill=self.color_accent, font=("Impact", 10), justify="center")

        elif side == "right":
            # 1. 顶部状态列表 (紧凑布局，从y=10开始，行距22)
            self.draw_vertical_stripes(canvas, 10, 0, h, 30)
            
            x_base = 60
            y_base = 20 
            statuses = ["GYRO: STABLE", "TEMP: 450K", "FUEL: 98%", "AMMO: NULL", "LINK: OK", "PING: 12ms"]
            for s in statuses:
                canvas.create_rectangle(x_base, y_base, x_base+5, y_base+5, fill=self.color_main)
                canvas.create_text(x_base+15, y_base+3, text=s, fill=self.color_main, font=("Consolas", 10), anchor="w")
                y_base += 22 # 更加紧凑，给下面留空间
            
            # 2. 醒目警告标志 (黄色三角形) - 放在中间偏下
            icon_y = 175 # 调整坐标
            p1 = (95, icon_y)
            p2 = (65, icon_y + 50)
            p3 = (125, icon_y + 50)
            canvas.create_polygon(p1, p2, p3, outline=self.color_alert, fill="", width=3)
            canvas.create_text(95, icon_y + 30, text="!", fill=self.color_alert, font=("Impact", 24))

            # 3. PREPARING 警告 (新增)
            # 做一个简单的闪烁效果提示，静态绘制
            canvas.create_text(95, icon_y + 70, text="PREPARING...", fill=self.color_eva_red, font=("Impact", 12))
            
            # 4. NO SIGNAL 警告 (置底)
            canvas.create_rectangle(50, h-110, 140, h-10, fill=self.color_warning_bg, outline=self.color_eva_red)
            canvas.create_text(95, h-60, text="NO\nSIGNAL", fill=self.color_eva_red, font=("Impact", 14), justify="center")

    def draw_vertical_stripes(self, canvas, x_pos, y_start, y_end, width):
        gap = 40
        for y in range(y_start, y_end, gap):
            points = [x_pos, y, x_pos + width, y, x_pos + width, y + 20, x_pos, y + 20]
            canvas.create_polygon(points, fill="#111", outline=self.color_grid)
            canvas.create_line(x_pos, y, x_pos+width, y+20, fill=self.color_grid)

    def draw_radar_grid(self, cv, size, center, label_text):
        step = 40
        for i in range(0, size+1, step):
            cv.create_line(i, 0, i, size, fill="#081818")
            cv.create_line(0, i, size, i, fill="#081818")
        cv.create_line(center, 0, center, size, fill=self.color_grid, width=2)
        cv.create_line(0, center, size, center, fill=self.color_grid, width=2)
        for r in [50, 100, 130]:
            cv.create_oval(center-r, center-r, center+r, center+r, outline=self.color_dim, width=1)
        cv.create_text(center, size-20, text=label_text, fill="gray", font=("Impact", 10))

    # --- 交互逻辑 ---
    def bind_keyboard_events(self):
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)

    def on_key_press(self, event):
        key = event.keysym
        
        if key.lower() in self.keys_move:
            if not self.keys_move[key.lower()]: 
                self.keys_move[key.lower()] = True
                self.update_joy1_from_keys()
        
        elif key in self.keys_pose:
            self.last_pose_action_time = time.time()
            
            if not self.keys_pose[key]:
                # 刚按下立即触发一次
                self.keys_pose[key] = True
                self.step_pose_value(key)
                self.pose_key_timers[key] = time.time()

    def on_key_release(self, event):
        key = event.keysym
        if key.lower() in self.keys_move:
            self.keys_move[key.lower()] = False
            self.update_joy1_from_keys()
        elif key in self.keys_pose:
            self.keys_pose[key] = False
            if key in self.pose_key_timers:
                del self.pose_key_timers[key]
            self.last_pose_action_time = time.time()

    def update_joy1_from_keys(self):
        target_x = 0
        target_y = 0
        offset_speed = self.joy1_radius * 0.1 
        offset_turn = self.joy1_radius * 0.8 

        if self.keys_move['w']: target_y -= offset_speed 
        if self.keys_move['s']: target_y += offset_speed
        if self.keys_move['a']: target_x -= offset_turn 
        if self.keys_move['d']: target_x += offset_turn

        abs_x = self.joy1_center + target_x
        abs_y = self.joy1_center + target_y
        self.update_joy1_ui(abs_x, abs_y)
        
        speed_val = int(-target_y / self.joy1_radius * self.max_val_move)
        turn_val = int(-target_x / self.joy1_radius * self.max_val_move) 
        self.send_move_command(speed_val, turn_val, force=True)

    def on_drag_joy1(self, event):
        dx = event.x - self.joy1_center
        dy = event.y - self.joy1_center
        distance = math.sqrt(dx*dx + dy*dy)
        if distance > self.joy1_radius:
            ratio = self.joy1_radius / distance
            dx *= ratio
            dy *= ratio
        self.update_joy1_ui(self.joy1_center + dx, self.joy1_center + dy)
        speed_val = int(-dy / self.joy1_radius * self.max_val_move)
        turn_val = int(-dx / self.joy1_radius * self.max_val_move)
        self.send_move_command(speed_val, turn_val)

    def on_release_joy1(self, event):
        self.update_joy1_ui(self.joy1_center, self.joy1_center)
        self.send_move_command(0, 0, force=True) 
        if self.is_connected: self.send_raw_command("S")

    def update_joy1_ui(self, x, y):
        r = self.knob_radius
        self.canvas1.coords(self.knob1, x-r, y-r, x+r, y+r)
        gr = r + 8 
        self.canvas1.coords(self.knob1_glow, x-gr, y-gr, x+gr, y+gr)
        self.canvas1.coords(self.knob1_center, x-3, y-3, x+3, y+3)

    # --- 姿态控制逻辑 ---
    def step_pose_value(self, key):
        changed = False
        if key == 'Left':
            self.val_r -= self.step_r
            if self.val_r < self.min_r: self.val_r = self.min_r
            changed = True
        elif key == 'Right':
            self.val_r += self.step_r
            if self.val_r > self.max_r: self.val_r = self.max_r
            changed = True
        elif key == 'Up': 
            self.val_h += self.step_h
            if self.val_h > self.max_h: self.val_h = self.max_h
            changed = True
        elif key == 'Down':
            self.val_h -= self.step_h
            if self.val_h < self.min_h: self.val_h = self.min_h
            changed = True
            
        if changed:
            self.update_joy2_ui_from_val()
            self.send_pose_command()

    def check_pose_keys_loop(self):
        """长按检测：改为 0.1s 极速连发"""
        current_time = time.time()
        
        for key, start_time in list(self.pose_key_timers.items()):
            # 修改：这里从 0.5 减少到 0.1，实现快速增加档位
            if current_time - start_time >= 0.1:
                self.step_pose_value(key)
                self.pose_key_timers[key] = current_time 
                self.last_pose_action_time = current_time

        # 循环频率从 50ms 加快到 20ms，保证 0.1s 响应的准确性
        self.root.after(20, self.check_pose_keys_loop)

    def auto_return_loop(self):
        """自动回中：保持 0.5s 平滑复位"""
        current_time = time.time()
        
        if not any(self.keys_pose.values()) and not self.joy2_dragging:
            if current_time - self.last_pose_action_time > 1.0:
                if not hasattr(self, 'last_auto_return_tick'):
                    self.last_auto_return_tick = current_time
                
                if current_time - self.last_auto_return_tick >= 0.5:
                    changed = False
                    # R 回中
                    if abs(self.val_r - self.default_r) > 0.1:
                        if self.val_r > self.default_r:
                            self.val_r -= self.step_r
                            if self.val_r < self.default_r: self.val_r = self.default_r
                        else:
                            self.val_r += self.step_r
                            if self.val_r > self.default_r: self.val_r = self.default_r
                        changed = True
                        
                    # H 回中
                    if abs(self.val_h - self.default_h) > 0.1:
                        if self.val_h > self.default_h:
                            self.val_h -= self.step_h
                            if self.val_h < self.default_h: self.val_h = self.default_h
                        else:
                            self.val_h += self.step_h
                            if self.val_h > self.default_h: self.val_h = self.default_h
                        changed = True
                    
                    if changed:
                        self.update_joy2_ui_from_val()
                        self.send_pose_command()
                        
                    self.last_auto_return_tick = current_time
        else:
             self.last_auto_return_tick = time.time()

        self.root.after(100, self.auto_return_loop)

    # --- 摇杆2 拖拽 ---
    joy2_dragging = False

    def on_drag_joy2(self, event):
        self.joy2_dragging = True
        self.last_pose_action_time = time.time() 
        dx = event.x - self.joy2_center
        dy = event.y - self.joy2_center
        distance = math.sqrt(dx*dx + dy*dy)
        if distance > self.joy2_radius:
            ratio = self.joy2_radius / distance
            dx *= ratio
            dy *= ratio
        
        pct_x = dx / self.joy2_radius 
        pct_y = dy / self.joy2_radius 

        self.val_r = pct_x * self.max_r
        delta_h = self.max_h - self.default_h
        self.val_h = self.default_h - (pct_y * delta_h)

        self.val_r = max(self.min_r, min(self.max_r, self.val_r))
        self.val_h = max(self.min_h, min(self.max_h, self.val_h))

        self.update_joy2_ui(self.joy2_center + dx, self.joy2_center + dy)
        self.send_pose_command()

    def on_release_joy2(self, event):
        self.joy2_dragging = False
        self.last_pose_action_time = time.time()

    def update_joy2_ui_from_val(self):
        ratio_r = self.val_r / self.max_r
        dx = ratio_r * self.joy2_radius
        delta = self.val_h - self.default_h 
        ratio_h = - (delta / (self.max_h - self.default_h))
        dy = ratio_h * self.joy2_radius
        self.update_joy2_ui(self.joy2_center + dx, self.joy2_center + dy)

    def update_joy2_ui(self, x, y):
        r = self.knob_radius
        self.canvas2.coords(self.knob2, x-r, y-r, x+r, y+r)
        gr = r + 8 
        self.canvas2.coords(self.knob2_glow, x-gr, y-gr, x+gr, y+gr)
        self.canvas2.coords(self.knob2_center, x-3, y-3, x+3, y+3)
        self.lbl_r.config(text=f"{self.val_r:.1f}")
        self.lbl_h.config(text=f"{self.val_h:.1f}")

    # --- 串口通信 ---
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

    def send_move_command(self, m, t, force=False):
        if self.lbl_speed: self.lbl_speed.config(text=f"{m:+04d}")
        if self.lbl_turn: self.lbl_turn.config(text=f"{t:+04d}")
        
        current_time = time.time()
        if self.is_connected and self.ser and self.ser.is_open:
            if force or (current_time - self.last_send_time > self.send_interval):
                try:
                    if force or (m != self.last_sent_m):
                        self.ser.write(f"M{m}\r\n".encode('utf-8'))
                        self.last_sent_m = m
                        time.sleep(0.08)
                    if force or (t != self.last_sent_t):
                        self.ser.write(f"T{t}\r\n".encode('utf-8'))
                        self.last_sent_t = t
                    self.last_send_time = time.time()
                except Exception as e:
                    self.append_log(f"[TX] !! Send Error: {e}")

    def send_pose_command(self):
        if self.is_connected and self.ser and self.ser.is_open:
            try:
                # R格式：R5.0
                cmd_r = f"R{self.val_r:.2f}\r\n"
                self.ser.write(cmd_r.encode('utf-8'))
                
                time.sleep(0.02)
                
                # 【关键修复】H格式：h160.5,160.5 (去掉h后面的逗号)
                # 因为 C代码 &Serial_RxPacket[1] 是从第2个字符开始读的
                # 如果发 "h,160", C读到的是 ",160"，导致解析失败
                # 必须发 "h160", C读到的是 "160"，解析成功
                cmd_h = f"h{self.val_h:.2f},{self.val_h:.2f}\r\n"
                self.ser.write(cmd_h.encode('utf-8'))
                
            except Exception as e:
                self.append_log(f"[TX] !! Pose Send Error: {e}")

    def send_raw_command(self, cmd_str):
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