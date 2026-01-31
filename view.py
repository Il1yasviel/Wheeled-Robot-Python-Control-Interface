# -*- coding: utf-8 -*-
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
try:
    from ttkbootstrap.widgets.scrolled import ScrolledText 
except ImportError:
    from ttkbootstrap.scrolled import ScrolledText

from config import COLORS, DIMS
from widgets import JoystickWidget, DecorPanel, WarningStrip, EvaButton  # <--- 确保导入了 EvaButton


class MainView:
    def __init__(self, root, close_callback):
        self.root = root
        self.close_callback = close_callback
        
        # 窗口设置
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg="black")
        self.center_window(DIMS["width"], DIMS["height"])
        
        # 布局初始化
        self.setup_title_bar()
        self.setup_main_layout()
        self.setup_resize_grip()

    def center_window(self, w, h):
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def setup_title_bar(self):
        self.title_bar = tk.Frame(self.root, bg="black", relief="flat", bd=0)
        self.title_bar.pack(fill="x", side="top")
        
        title_lbl = tk.Label(self.title_bar, text="NEXUS-7 DUAL LINK CONTROLLER", 
                             bg="black", fg=COLORS["eva_red"], font=("Impact", 14))
        title_lbl.pack(side="left", padx=10, pady=5)
        
        close_btn = tk.Button(self.title_bar, text=" [ X ] ", command=self.close_callback,
                              bg="black", fg=COLORS["eva_red"], font=("Consolas", 12, "bold"), 
                              bd=0, activebackground=COLORS["eva_red"], activeforeground="black")
        close_btn.pack(side="right", padx=5, pady=5)
        
        # 拖动窗口逻辑绑定
        for widget in [self.title_bar, title_lbl]:
            widget.bind("<Button-1>", self._get_pos)
            widget.bind("<B1-Motion>", self._move_window)

    def setup_main_layout(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)

        # 1. 顶部连接栏
        self._setup_connection_bar(main_frame)
        
        # 2. 警告带
        WarningStrip(main_frame, width=DIMS["width"], height=80).pack(fill="x")

        # 3. 中间控制区
        middle = ttk.Frame(main_frame)
        middle.pack(fill="x", pady=10)
        
        # 左装饰
        DecorPanel(middle, "left", DIMS["joy_size"]).pack(side="left")
        
        # 摇杆 1 (WASD)
        self.joy1 = JoystickWidget(middle, DIMS["joy_size"], "LOCOMOTION", COLORS["accent"])
        self.joy1.pack(side="left", padx=5)
        
        # 数据仪表盘
        self._setup_dashboard(middle)
        
        # 摇杆 2 (姿态)
        self.joy2 = JoystickWidget(middle, DIMS["joy_size"], "ATTITUDE CTL", COLORS["sec_joy"])
        self.joy2.pack(side="left", padx=5)
        
        # 右装饰
        DecorPanel(middle, "right", DIMS["joy_size"]).pack(side="left")

        # 4. 日志区
        self._setup_log_area(main_frame)

    def _setup_connection_bar(self, parent):
        frame = ttk.Frame(parent, padding=(10, 5))
        frame.pack(fill="x")
        header = ttk.Frame(frame)
        header.pack(fill="x")
        
        # 左侧标题保持不变
        ttk.Label(header, text="/// SYSTEM LINK // OMEGA LEVEL", font=("Impact", 16), 
                  foreground=COLORS["main"]).pack(side="left")
        
        # 右侧总容器
        conn_frame = ttk.Frame(header)
        conn_frame.pack(side="right")
        
        # --- 1. 串口部分 (SRL) ---
        serial_sub = ttk.Frame(conn_frame)
        serial_sub.pack(side="left", padx=10)
        
        ttk.Label(serial_sub, text="SRL>", font=("Consolas", 9), foreground="gray").pack(side="left")
        self.port_combo = ttk.Combobox(serial_sub, width=10, font=("Consolas", 10))
        self.port_combo.pack(side="left", padx=2)
        
        self.btn_scan = ttk.Button(serial_sub, text="SCAN", bootstyle="outline-info", width=5)
        self.btn_scan.pack(side="left", padx=2)
        
        self.btn_connect = ttk.Button(serial_sub, text="CONNECT", bootstyle="success-outline", width=10)
        self.btn_connect.pack(side="left", padx=2)

        # --- 中间装饰分割线 ---
        ttk.Label(conn_frame, text="|", foreground=COLORS["grid"]).pack(side="left", padx=5)

        # --- 2. TCP 部分 (NET) ---
        tcp_sub = ttk.Frame(conn_frame)
        tcp_sub.pack(side="left", padx=10)
        
        ttk.Label(tcp_sub, text="NET>", font=("Consolas", 9), foreground="gray").pack(side="left")
        
        from config import TCP_CONFIG
        self.entry_ip = ttk.Entry(tcp_sub, width=14, font=("Consolas", 10))
        self.entry_ip.insert(0, TCP_CONFIG["default_ip"])
        self.entry_ip.pack(side="left", padx=2)
        
        self.entry_port = ttk.Entry(tcp_sub, width=5, font=("Consolas", 10))
        self.entry_port.insert(0, str(TCP_CONFIG["default_port"]))
        self.entry_port.pack(side="left", padx=2)
        
        self.btn_tcp_connect = ttk.Button(tcp_sub, text="LINK", bootstyle="success-outline", width=8)
        self.btn_tcp_connect.pack(side="left", padx=2)

# --- 替换 _setup_dashboard 方法 ---
    def _setup_dashboard(self, parent):
        panel = tk.Frame(parent, bg="black", width=120)
        panel.pack(side="left", fill="y", padx=5)
        
        def create_metric(label, default_val, color):
            tk.Label(panel, text=label, fg="gray", bg="black", font=("Consolas", 8)).pack(pady=(5,0))
            lbl = tk.Label(panel, text=default_val, fg=color, bg="black", font=("Orbitron", 14))
            lbl.pack()
            return lbl

        # 原有的仪表
        self.lbl_speed = create_metric("SPD (M)", "+000", COLORS["main"])
        self.lbl_turn = create_metric("TRN (T)", "+000", COLORS["main"])
        
        tk.Frame(panel, height=2, bg=COLORS["grid"]).pack(fill="x", pady=10)
        
        self.lbl_r = create_metric("ROLL (R)", "0.0", COLORS["sec_joy"])
        self.lbl_h = create_metric("HGT (H)", "110.0", COLORS["sec_joy"])

        tk.Frame(panel, height=2, bg=COLORS["grid"]).pack(fill="x", pady=10)

        # --- 新增：机械零点调节区域 (纯正 EVA 风格) ---
        tk.Label(panel, text="ZERO ADJ (P7)", fg=COLORS["eva_red"], bg="black", font=("Impact", 10)).pack(pady=(5, 5))
        
        # 容器
        adj_frame = tk.Frame(panel, bg="black")
        adj_frame.pack(pady=0)

        # 1. 上按钮 (使用自定义 EvaButton)
        # 注意：command 暂时留空，我们在 main.py 里通过 config 配置
        self.btn_zero_up = EvaButton(adj_frame, width=60, height=25, text="▲", font_size=10)
        self.btn_zero_up.pack(side="top", pady=2)

        # 2. 输入框 (自定义红色边框)
        # 原理：外层 Frame 是红色，内层 Entry 是黑色，padding=1 露出红色边框
        border_frame = tk.Frame(adj_frame, bg=COLORS["eva_red"], padx=1, pady=1)
        border_frame.pack(side="top", pady=4)
        
        self.entry_zero = tk.Entry(border_frame, bg="black", fg=COLORS["eva_red"], 
                                   insertbackground=COLORS["eva_red"], # 光标颜色
                                   font=("Consolas", 12, "bold"), 
                                   width=5, justify="center", 
                                   bd=0, highlightthickness=0) # 去掉原生边框
        self.entry_zero.pack()

        # 3. 下按钮 (使用自定义 EvaButton)
        self.btn_zero_down = EvaButton(adj_frame, width=60, height=25, text="▼", font_size=10)
        self.btn_zero_down.pack(side="top", pady=2)

    def _setup_log_area(self, parent):
        container = ttk.Frame(parent, padding=(10, 10))
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="NEURAL LINK LOG // RX_DATA_STREAM", 
                  font=("Consolas", 9), foreground=COLORS["main"]).pack(anchor="w")
        
        self.console = ScrolledText(container, font=("Consolas", 10), bootstyle="secondary", height=5)
        self.console.pack(fill="both", expand=True)
        self.console.text.configure(bg="#020a0a", fg=COLORS["text_log"], insertbackground="white")

    def setup_resize_grip(self):
        grip = ttk.Sizegrip(self.root, bootstyle="secondary")
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<B1-Motion>", self._on_resize)

    # --- 窗口操作辅助 ---
    def _get_pos(self, event):
        self.x_click = event.x
        self.y_click = event.y

    def _move_window(self, event):
        self.root.geometry(f"+{event.x_root - self.x_click}+{event.y_root - self.y_click}")

    def _on_resize(self, event):
        x1 = self.root.winfo_pointerx()
        y1 = self.root.winfo_pointery()
        x0 = self.root.winfo_rootx()
        y0 = self.root.winfo_rooty()
        self.root.geometry(f"{x1-x0}x{y1-y0}")

    def log(self, text):
        self.console.insert(tk.END, f"{text}\n")
        self.console.see(tk.END)