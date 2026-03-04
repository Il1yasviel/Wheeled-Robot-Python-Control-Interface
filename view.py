# -*- coding: utf-8 -*-
import tkinter as tk
import cv2
import ttkbootstrap as ttk  # 引入美化版 Tk 组件库
from ttkbootstrap.constants import * # 引入 UI 布局常量（如 LEFT, BOTH 等）
from PIL import Image, ImageTk  # 仅保留图像格式转换功能，用于显示
import json


# 尝试兼容不同版本的 ttkbootstrap 导入滚动文本框组件
try:
    from ttkbootstrap.widgets.scrolled import ScrolledText 
except ImportError:
    from ttkbootstrap.scrolled import ScrolledText

# 导入外部定义的视觉配置与自定义组件        
from config import COLORS, DIMS,TCP_CONFIG
from widgets import JoystickWidget, DecorPanel, WarningStrip, EvaButton 

class MainView:
    def __init__(self, root, close_callback):
        """
        初始化主视图界面
        :param root: 根窗口对象
        :param close_callback: 窗口关闭时的回调函数（用于清理资源）
        """
        self.root = root
        self.close_callback = close_callback
        
        
        # --- 窗口物理特性设置 ---
        self.root.overrideredirect(True)      # 强行移除系统原生标题栏（实现无边框 NERV 风格）
        self.root.attributes('-topmost', True) # 窗口始终置顶，确保在“战斗”中不被遮挡
        self.root.configure(bg="black")       # 全局背景设为极简深邃黑
        self.center_window(DIMS["width"], DIMS["height"]) # 将窗口居中放置
        
        # --- 界面组件初始化 ---
        self.setup_title_bar()   # 构建自定义的顶部拖动手柄
        self.setup_main_layout() # 构建核心 UI 结构
        self.setup_resize_grip() # 添加右下角的缩放手柄

    def center_window(self, w, h):
        """根据屏幕分辨率自动居中窗口的数学计算"""
        ws = self.root.winfo_screenwidth()  # 获取当前屏幕总宽度
        hs = self.root.winfo_screenheight() # 获取当前屏幕总高度
        x = (ws/2) - (w/2)                  # 计算水平偏移量
        y = (hs/2) - (h/2)                  # 计算垂直偏移量
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y)) # 设置窗口尺寸与位置坐标

    def setup_title_bar(self):
        """由于取消了原生边框，这里手动打造一个支持拖拽的伪标题栏"""
        self.title_bar = tk.Frame(self.root, bg="black", relief="flat", bd=0) # 标题栏容器
        self.title_bar.pack(fill="x", side="top") # 填充顶部空间
        
        # 标题文字：显示系统型号 NEXUS-7
        title_lbl = tk.Label(self.title_bar, text="2022023637陈浩 轮足机器人控制界面", 
                             bg="black", fg=COLORS["eva_red"], font=("Impact", 14))
        title_lbl.pack(side="left", padx=10, pady=5)
        
        # 关闭按钮：[ X ] 样式，红色高亮
        close_btn = tk.Button(self.title_bar, text=" [ X ] ", command=self.close_callback,
                              bg="black", fg=COLORS["eva_red"], font=("Consolas", 12, "bold"), 
                              bd=0, activebackground=COLORS["eva_red"], activeforeground="black")
        close_btn.pack(side="right", padx=5, pady=5)  #pad用于x方向和y方向偏离的像素，这里主要是上下左右都有间距值，起到小居中的作用
        
        # 核心逻辑：绑定鼠标点击和移动事件，使标题栏具备拖拽移动窗口的功能
        for widget in [self.title_bar, title_lbl]:    #遍历这标题栏和标题文字，给这两个东西绑定事件
            widget.bind("<Button-1>", self._get_pos)     # 记录点击瞬间的坐标
            widget.bind("<B1-Motion>", self._move_window) # 随鼠标移动实时更新窗口位置

    def setup_main_layout(self):
        """
        ★ 核心重构：将界面划分为左右两个独立区域
        """
        # 全局主容器
        self.main_container = tk.Frame(self.root, bg="black")
        self.main_container.pack(fill="both", expand=True, padx=2, pady=2)

        # === 左侧：控制面板区域 (Left Panel) ===
        self.left_panel = tk.Frame(self.main_container, bg="black", width=DIMS["left_son2_width"])
        self.left_panel.pack(side="left", fill="y", padx=(0, 5))
        self.left_panel.pack_propagate(False) # 强制左侧固定宽度，防止被右侧挤压
        
        # 填充左侧内容（原来的控件）
        self._init_control_widgets(self.left_panel)

        # === 右侧：视频监控区域 (Right Panel) ===
        self.right_panel = tk.Frame(self.main_container, bg="#080808", bd=1, relief="sunken")
        self.right_panel.pack(side="right", fill="both", expand=True)
        
        # 填充右侧内容（新的视频组件）
        self._init_video_widgets(self.right_panel)


    def _init_control_widgets(self, parent):
        """
        构建原来的仪表盘、摇杆等组件
        """
        # 1. 顶部连接栏
        self._setup_connection_bar(parent)
        
        # 2. 警告条            width的值和上面数24行的容器宽度要保持一致
        WarningStrip(parent, width=DIMS["left_son2_width"], height=100).pack(fill="x")
        
        # 3. 中间控制区
        middle = ttk.Frame(parent)
        middle.pack(fill="x", pady=10)
         # 左装饰面板                 传入画布的宽度和长度，想要多大的画布
        DecorPanel(middle, "left", DIMS["decor_width"], DIMS["joy_size"]).pack(side="left")
        #左摇杆
        self.joy1 = JoystickWidget(middle, DIMS["joy_size"], "LOCOMOTION", COLORS["accent"])
        self.joy1.pack(side="left", padx=5)
        #中间的仪表盘，显示摇杆数值之类的
        self._setup_dashboard(middle) 
        #右摇杆
        self.joy2 = JoystickWidget(middle, DIMS["joy_size"], "ATTITUDE", COLORS["sec_joy"])
        self.joy2.pack(side="left", padx=5)
        DecorPanel(middle, "right",DIMS["decor_width"] ,DIMS["joy_size"]).pack(side="left")

        # 4. 底部日志
        self._setup_log_area(parent)




    def _init_video_widgets(self, parent):
        """
        构建右侧视频显示区的容器结构
        """
        # 顶部 HUD 装饰
        header = tk.Frame(parent, bg="black", height=30)
        header.pack(fill="x", side="top", pady=(5,0))
        
        tk.Label(header, text="/// OPTICAL FEED", fg=COLORS["eva_red"], bg="black", 
                 font=("Consolas", 14, "bold")).pack(side="left", padx=10)
        

        # =========================================================
        # ★ 核心修改：放弃 Label，改用 Canvas 来显示环境数据        Label受到限制，无论如何都没法改变字体的颜色，强行改变太复杂了
        # =========================================================
        # 创建一个小画布，高度30，宽度足够容纳文字(比如400)，背景黑，无边框
        self.env_canvas = tk.Canvas(header, bg="black", height=30, width=550, highlightthickness=0)
        self.env_canvas.pack(side="left", padx=10,fill="x", expand=True)

        # 在画布上直接画文字！
        # 参数说明：
        # 0, 15: 文字左侧中间的坐标 (x=0, y=高度的一半)
        # text: 初始文字
        # fill: 文字颜色 (强制亮红，不受主题影响)
        # font: 字体设置
        # anchor="w": 锚点设为西(左)侧，保证文字从左往右排列
        self.env_text_id = self.env_canvas.create_text(0, 15, 
                                                       text="ENV: SCANNING...", 
                                                       fill="#FF3333", 
                                                       font=("Consolas", 14, "bold"), 
                                                       anchor="w")
        # =========================================================


        # 这里只放置一个 Label 用于显示 FPS，具体数值由外部更新
        self.fps_label = tk.Label(header, text="STANDBY", fg="gray", bg="black", font=("Consolas", 10))
        self.fps_label.pack(side="right", padx=10)

        # =========================================================
        # ★ 核心修改 2：在视频下方新建 AI 对话区域
        # =========================================================
        self.chat_frame = tk.Frame(parent, bg="#080808", height=180) # 固定高度 180
        self.chat_frame.pack(side="bottom", fill="x", padx=5, pady=(0, 5))
        self.chat_frame.pack_propagate(False) # 强制固定高度，不被内部组件撑开

        # 对话框标题
        tk.Label(self.chat_frame, text="/// AI COMM LINK // NEURAL DIALOGUE", 
                 fg=COLORS["eva_red"], bg="#080808", font=("Consolas", 10, "bold")).pack(anchor="w", padx=5)

        # 滚动对话文本框
        self.chat_console = ScrolledText(self.chat_frame, font=("Microsoft YaHei", 10), bootstyle="secondary")
        self.chat_console.pack(fill="both", expand=True, padx=5, pady=2)
        # 设置深色背景和默认文字颜色
        self.chat_console.text.configure(bg="#020a0a", fg="#00FF00", insertbackground="white")
        
        # 定义不同角色的颜色标签，方便显示不同的颜色
        self.chat_console.text.tag_config("user", foreground="#00FFFF") # 玩家发出的文字是青色
        self.chat_console.text.tag_config("ai", foreground="#33FF33")   # AI 的文字是亮绿色
        self.chat_console.text.tag_config("system", foreground="gray")  # 系统提示是灰色

        # ★ 核心画布：Canvas
        # 使用 Canvas 而不是 Label，因为 Canvas 缩放性能更好，且方便后续画覆盖层（准星等）
        self.video_canvas = tk.Canvas(parent, bg="#020202", highlightthickness=0)
        self.video_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 绘制初始的等待画面
        w = 640; h = 480
        self.video_canvas.create_text(w/2, h/2, text="WAITING FOR SIGNAL...", 
                                      fill="gray", font=("Impact", 20), tags="status_text")
        


    # =========================================================
    # ★ 新增方法：供主程序调用，向聊天框追加文字
    # =========================================================
    def append_chat(self, role, text, end=""):
        """向 AI 聊天框追加文字"""
        # 根据角色选择颜色标签
        tag = "system"
        if role == "User": tag = "user"
        elif role == "AI": tag = "ai"

        # 插入文字并应用颜色标签
        self.chat_console.text.insert(tk.END, text + end, tag)
        self.chat_console.text.see(tk.END) # 自动滚动到底部





    def update_env_data(self, text):
        """更新环境数据 (含判空与基准扣除算法)"""
        if not text: return
        try:
            data = json.loads(text)
            
            # 1. 温湿度
            temp = data.get("temp")
            humi = data.get("humi")
            temp_str = f"{temp:02d}" if temp is not None else "--"
            humi_str = f"{humi:02d}" if humi is not None else "--"
            
            # 2. 气体浓度 (零点校准)
            gas_raw = data.get("gas_raw")
            alc_str = "--"
            text_color = "#33FF33" # 默认绿

            if gas_raw is not None:
                # --- 参数配置 ---
                ZERO_POINT = 175     # 你的环境底噪 (Raw)
                SENSITIVITY = 0.2    # 放大倍数
                ADC_SCALE = 1.7578125 
                # ---------------

                if gas_raw <= ZERO_POINT:
                    alc_percent = 0.0
                else:
                    # 增量算法
                    delta = gas_raw - ZERO_POINT
                    alc_percent = delta * SENSITIVITY
                
                if alc_percent > 100.0: alc_percent = 100.0
                alc_str = f"{alc_percent:.1f}%"
                
                if alc_percent > 20.0: text_color = "#FF3333" # 报警红
            
            display_text = f"/// TEMP: {temp_str}°C   HUMI: {humi_str}%   ALC: {alc_str}"
            self.env_canvas.itemconfigure(self.env_text_id, text=display_text, fill=text_color)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"UI update error: {e}")


    # ==================================================
    #  对外接口 (API) - 供主控逻辑调用
    # ==================================================
    
    def update_video_frame(self, cv_image, fps_text=""):
        """
        更新视频画面。
        :param cv_image: OpenCV 格式的图像 (BGR numpy array)
        :param fps_text: 状态栏显示的文字
        """
        if cv_image is None: 
            return

        # 1. 获取 Canvas 当前的实际尺寸 (实现自适应缩放)
        canvas_width = self.video_canvas.winfo_width()
        canvas_height = self.video_canvas.winfo_height()
        
        # 避免窗口刚初始化时尺寸为 1x1 报错
        if canvas_width < 10 or canvas_height < 10:
            return

        # 2. 格式转换 BGR -> RGB -> PIL
        # 注意：这里假设传入的是 BGR (OpenCV默认)，如果是 RGB 需调整
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)

        # 3. 图像缩放 (Resize) 以适应 Canvas
        # 使用 LANCZOS 算法保持画质，或者使用 NEAREST 追求速度
        pil_image = pil_image.resize((canvas_width, canvas_height), Image.Resampling.NEAREST)

        # 4. 转为 Tkinter 兼容对象
        self.current_photo = ImageTk.PhotoImage(pil_image)

        # 5. 绘制到 Canvas
        # create_image 如果 ID 已存在会创建新的，建议只更新 image 属性，这里简化为覆盖
        self.video_canvas.create_image(0, 0, image=self.current_photo, anchor="nw")
        
        # 6. 更新 FPS 文字
        if fps_text:
            self.fps_label.config(text=fps_text, fg=COLORS["main"])


    def update_log(self, text):
        """外部调用写日志"""
        self.console.insert(tk.END, f"{text}\n")
        self.console.see(tk.END)


    def _setup_connection_bar(self, parent):
        """构建连接参数设置行"""
        frame = ttk.Frame(parent, padding=(10, 5))
        frame.pack(fill="x")
        header = ttk.Frame(frame)
        header.pack(fill="x")
        
        # 左侧显示的系统运行等级标签
        ttk.Label(header, text="/// SYSTEM LINK // OMEGA LEVEL", font=("Impact", 16), 
                  foreground=COLORS["main"]).pack(side="left")
        
        # 右侧的功能按钮容器
        conn_frame = ttk.Frame(header)
        conn_frame.pack(side="right")
        
        # --- 串口设置区域 (Serial Link) ---
        serial_sub = ttk.Frame(conn_frame)
        serial_sub.pack(side="left", padx=10)
        ttk.Label(serial_sub, text="SRL>", font=("Consolas", 9), foreground="gray").pack(side="left")
        self.port_combo = ttk.Combobox(serial_sub, width=10, font=("Consolas", 10)) # 串口选择下拉框
        self.port_combo.pack(side="left", padx=2)
        self.btn_scan = ttk.Button(serial_sub, text="SCAN", bootstyle="outline-info", width=5) # 扫描按钮
        self.btn_scan.pack(side="left", padx=2)
        self.btn_connect = ttk.Button(serial_sub, text="CONNECT", bootstyle="success-outline", width=10) # 串口连接按钮
        self.btn_connect.pack(side="left", padx=2)

        # 视觉分割符号 "|"
        ttk.Label(conn_frame, text="|", foreground=COLORS["grid"]).pack(side="left", padx=5)

        # --- TCP 网络设置区域 (Network Link) ---
        tcp_sub = ttk.Frame(conn_frame)
        tcp_sub.pack(side="left", padx=10)
        ttk.Label(tcp_sub, text="NET>", font=("Consolas", 9), foreground="gray").pack(side="left")
        
        self.entry_ip = ttk.Entry(tcp_sub, width=14, font=("Consolas", 10)) # IP 输入框
        self.entry_ip.insert(0, TCP_CONFIG["default_ip"]) # 填充默认 IP
        self.entry_ip.pack(side="left", padx=2)
        
        self.entry_port = ttk.Entry(tcp_sub, width=5, font=("Consolas", 10)) # 端口输入框
        self.entry_port.insert(0, str(TCP_CONFIG["default_port"])) # 填充默认端口
        self.entry_port.pack(side="left", padx=2)
        
        self.btn_tcp_connect = ttk.Button(tcp_sub, text="LINK", bootstyle="success-outline", width=8) # TCP 连接按钮
        self.btn_tcp_connect.pack(side="left", padx=2)

    def _setup_dashboard(self, parent):
        """中间垂直排列的数据监控面板"""
        panel = tk.Frame(parent, bg="black", width=120)
        panel.pack(side="left", fill="y", padx=5)
        
        def create_metric(label, default_val, color):
            """内部工具函数：创建一个数据读数模块（包含标题和数值）"""
            tk.Label(panel, text=label, fg="gray", bg="black", font=("Consolas", 8)).pack(pady=(5,0))
            lbl = tk.Label(panel, text=default_val, fg=color, bg="black", font=("Orbitron", 14)) # 使用 Orbitron 字体增强科幻感
            lbl.pack()
            return lbl

        # 创建四个主要监控项：速度、转向、横滚角、高度
        self.lbl_speed = create_metric("SPD (M)", "+000", COLORS["main"])
        self.lbl_turn = create_metric("TRN (T)", "+000", COLORS["main"])
        tk.Frame(panel, height=2, bg=COLORS["grid"]).pack(fill="x", pady=10) # 装饰分割线
        
        self.lbl_r = create_metric("ROLL (R)", "0.0", COLORS["sec_joy"])
        self.lbl_h = create_metric("HGT (H)", "110.0", COLORS["sec_joy"])
        tk.Frame(panel, height=2, bg=COLORS["grid"]).pack(fill="x", pady=10)

        # --- 零点微调区域 (Zero Point Adjustment) ---
        tk.Label(panel, text="ZERO ADJ (P7)", fg=COLORS["eva_red"], bg="black", font=("Impact", 10)).pack(pady=(5, 5))
        adj_frame = tk.Frame(panel, bg="black") # 调节区域容器
        adj_frame.pack(pady=0)

        # 向上微调按钮 (自定义 EvaButton)
        self.btn_zero_up = EvaButton(adj_frame, width=60, height=25, text="▲", font_size=10)
        self.btn_zero_up.pack(side="top", pady=2)

        # 具有红色发光边框的 Entry (通过嵌套 Frame 实现像素边框)
        border_frame = tk.Frame(adj_frame, bg=COLORS["eva_red"], padx=1, pady=1)
        border_frame.pack(side="top", pady=4)
        self.entry_zero = tk.Entry(border_frame, bg="black", fg=COLORS["eva_red"], 
                                   insertbackground=COLORS["eva_red"], # 红色输入光标
                                   font=("Consolas", 12, "bold"), 
                                   width=5, justify="center", 
                                   bd=0, highlightthickness=0) # 无原生边框
        self.entry_zero.pack()

        # 向下微调按钮
        self.btn_zero_down = EvaButton(adj_frame, width=60, height=25, text="▼", font_size=10)
        self.btn_zero_down.pack(side="top", pady=2)

    def _setup_log_area(self, parent):
        """
        底部的系统运行日志终端 + 云台控制区
        """
        container = ttk.Frame(parent, padding=(10, 10))
        container.pack(fill="both", expand=True)

        # A. 左侧面板：日志区 (使用 expand=True 让它占据剩余空间)
        left_panel = ttk.Frame(container)
        left_panel.pack(side="left", fill="both", expand=True)

        # 日志区域标签
        ttk.Label(left_panel, text="NEURAL LINK LOG // RX_DATA_STREAM", 
                  font=("Consolas", 9), foreground=COLORS["main"]).pack(anchor="w")
        
        # 滚动文本框：显示接收到的原始指令或系统状态
        self.console = ScrolledText(left_panel, font=("Consolas", 10), bootstyle="secondary", height=5)
        self.console.pack(fill="both", expand=True)
        # 定制控制台背景色（深墨绿黑）和文字颜色（电网绿）
        self.console.text.configure(bg="#020a0a", fg=COLORS["text_log"], insertbackground="white")



        # B. 右侧面板：云台控制区 (固定宽度，靠右)
        right_panel = ttk.Frame(container)
        right_panel.pack(side="right", fill="y", padx=(10, 0)) # padx 左边留点空隙隔开日志

        # === 2. 新增云台摇杆代码 (放入 right_panel) ===
        # 云台区域标签，和摇杆处于同一容器
        ttk.Label(right_panel, text="GIMBAL // MANUAL_OVERRIDE", 
                  font=("Consolas", 9), foreground=COLORS["alert"]).pack(anchor="w")
        
        self.joy_gimbal = JoystickWidget(right_panel, size=120, label="PAN/TILT", color_theme=COLORS["alert"])
        self.joy_gimbal.pack(side="top", pady=5) 



        # === 【新增】控制开关变量与按钮 ===
        # 1. 初始化一个变量，默认设为 False (不生效)
        self.gimbal_override_enabled = False 
        
        # 2. 创建一个按钮
        self.btn_gimbal_override = ttk.Button(
            right_panel, 
            text="MANUAL: FALSE", 
        )
        self.btn_gimbal_override.pack(side="top", pady=5, fill="x")


        

    def setup_resize_grip(self):
        """在窗口右下角添加一个微小的拉伸柄，以便手动调整窗口大小"""
        grip = ttk.Sizegrip(self.root, bootstyle="secondary")
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<B1-Motion>", self._on_resize) # 绑定缩放处理函数

    # --- 窗口交互底层辅助函数 ---
    def _get_pos(self, event):
        """记录鼠标点击时的初始相对位置"""
        self.x_click = event.x
        self.y_click = event.y

    def _move_window(self, event):
        """根据鼠标位移差量移动整个主窗口"""
        self.root.geometry(f"+{event.x_root - self.x_click}+{event.y_root - self.y_click}")

    def _on_resize(self, event):
        """根据鼠标在全球坐标系下的位置重新计算窗口宽高"""
        x1 = self.root.winfo_pointerx() # 当前鼠标 X 坐标
        y1 = self.root.winfo_pointery() # 当前鼠标 Y 坐标
        x0 = self.root.winfo_rootx()    # 窗口左上角 X 坐标
        y0 = self.root.winfo_rooty()    # 窗口左上角 Y 坐标
        self.root.geometry(f"{x1-x0}x{y1-y0}") # 动态拉伸 geometry

    def log(self, text):
        """公共方法：向控制台末尾追加一条日志信息，并自动滚动到底部"""
        self.console.insert(tk.END, f"{text}\n")
        self.console.see(tk.END) # 保持视图在最新一行