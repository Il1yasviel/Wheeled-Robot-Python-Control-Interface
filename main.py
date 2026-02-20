# -*- coding: utf-8 -*-
# 导入 Python 内置 GUI 库 tkinter
import tkinter as tk
# 导入美化版的 tkinter 库 ttkbootstrap，用于创建更现代的界面
import ttkbootstrap as ttk
# 导入数学计算、时间处理和日期处理库
import math, time, datetime
import time

# 从自定义配置文件中导入颜色、尺寸和参数常量
from config import COLORS, DIMS, PARAMS,UDP_CONFIG
# 从自定义视图模块导入主视图界面类
from view import MainView
# 从自定义通信模块导入混合通信服务类（支持串口和网络）
from comms import HybridService,GimbalUDPService
#导入视频相关的
from vision_service import VisionService 
# 导入新写的服务
from sensor_service import SensorService 


class Controller:
    def __init__(self):
        # 初始化主窗口，并应用 "cyborg"（赛博朋克风格）主题
        self.root = ttk.Window(themename="cyborg")
        # 实例化视图类，并将窗口对象和关闭回调函数传入
        self.view = MainView(self.root, self.close_app)
        # 实例化通信服务类(串口和TCP的对象)，并传入日志记录函数以便在界面显示信息
        self.comms = HybridService(self.log_msg)

        self.is_drawing = False         # 1. 增加一个锁标记，来不及处理的图片就直接丢掉，否则会变得越来越卡


        # 1. 初始化逻辑控制变量，控制云台摇杆是否生效，为了实现自动化和手动控制不冲突
        self.gimbal_override_enabled = False 

        #舵机角度的全局变量
        self.current_pan = 90
        self.current_tilt = 90

        # 实例化云台服务
        self.gimbal_service = GimbalUDPService(UDP_CONFIG["RK3506_ip"], UDP_CONFIG["RK3506_UDP_port"])
        # === 新增：云台控制相关变量 ===
        self.val_pan = 90  # 左右舵机默认角度
        self.val_tilt = 90 # 上下舵机默认角度
        self.joy_gimbal_dragging = False # 云台摇杆是否被拖动标志


        # --- 运动状态变量 (核心状态) ---
        self.val_m = 0      # 存储当前的前进/后退速度 (Movement)
        self.val_t = 0      # 存储当前的左右转向值 (Turnment)
        self.val_r = 0.0    # 存储当前的机身翻滚角 (Roll)
        self.val_h = PARAMS["h_default"] # 初始化机身高度为配置文件中的默认值 (Height)
        self.val_zero = 0.0 # 存储机械零点偏置值 (Mechanical Zero)

        # 键盘按键状态字典，用于判断 WASD 是否被按下（实现多键并按）
        self.keys_move = {'w': False, 's': False, 'a': False, 'd': False}
        # 姿态调整按键状态字典（上下左右方向键）
        self.keys_pose = {'Up': False, 'Down': False, 'Left': False, 'Right': False}
        
        # 标记位：记录虚拟摇杆 1（左侧，控制移动）和摇杆 2（右侧，控制姿态）是否正在被鼠标拖动
        self.joy2_dragging = False
        self.joy1_dragging = False 
        
        # 记录上一次发送指令的时间戳，用于控制发送频率（防止堵塞缓冲区）
        self.last_send_time = 0
        
        # 初始化界面上“机械零点”的默认值
        try:
            # 从界面输入框获取字符串并去除空格
            z_str = self.view.entry_zero.get().strip()
            # 如果不为空则转为浮点数，否则默认为 0.0
            self.val_zero = float(z_str) if z_str else 0.0
        except:
            # 出现异常（如输入非数字）则设为 0
            self.val_zero = 0.0

        # 执行事件绑定（将按钮点击、按键按下等与函数关联）
        self.bind_events()
        # 初始扫描一次可用的串口
        self.refresh_ports()


        # ========================================================
        # 启动视觉检测线程
        # ========================================================
        # 视频流地址
        video_url = "http://192.168.10.114:8080/?action=stream" 
        
        # 1. 实例化 VisionService
        # 参数1: 地址, 参数2: 这里的 self.update_vision_ui 是回调函数
        self.vision_thread = VisionService(video_url, self.update_vision_ui)
        
        # 2. 设置为守护线程 (Daemon)，这样主程序关闭时它也会跟着死，不会卡在后台
        self.vision_thread.daemon = True 
        
        # 3. 开始运行
        self.vision_thread.start()
        # ========================================================


        # 开发板 IP 是这个，端口是 8888
        target_ip = UDP_CONFIG["RK3506_ip"] 
        target_port = UDP_CONFIG["RK3506_sensor_port"]
        
        self.sensor_thread = SensorService(target_ip, target_port, self.update_sensor_ui)
        self.sensor_thread.daemon = True # 守护线程，主程序关了它也关
        self.sensor_thread.start()





        # 启动“心跳”循环函数，该函数会每隔 50ms 自动运行一次，负责实时更新和发包
        self.heartbeat_loop()

        # 进入 tkinter 的主事件循环，开始监听所有用户交互
        self.root.mainloop()


    # ============================================================
    # ★ 传感器回调函数
    # ============================================================
    def update_sensor_ui(self, text):
        """
        这个函数由 SensorService 子线程调用。
        必须通过 root.after 扔回主线程更新 UI。
        """
        self.root.after(0, lambda: self.view.update_env_data(text))

    # ============================================================
    # ★ 统一的关闭程序函数 (合并了视觉、传感器和串口清理)
    # ============================================================
    def close_app(self):
        print("--- Closing App & Stopping Threads ---")
        
        # 1. 停止视觉线程
        if hasattr(self, 'vision_thread'):
            try:
                self.vision_thread.stop()
                print("Vision thread stopped.")
            except Exception as e:
                print(f"Error stopping vision: {e}")
        
        # 2. 停止传感器线程 (如果不加这步，关闭窗口后后台还会报错)
        if hasattr(self, 'sensor_thread'):
            try:
                self.sensor_thread.stop()
                print("Sensor thread stopped.")
            except Exception as e:
                print(f"Error stopping sensor: {e}")

        # 3. 断开底层通信 (串口/TCP)
        if hasattr(self, 'comms'):
            self.comms.disconnect()
            print("Comms disconnected.")

        # 4. 销毁主窗口
        try:
            self.root.destroy()
            print("Window destroyed.")
        except Exception as e:
            print(f"Error destroying window: {e}")



    # ============================================================
    # ★ 新增：视觉回调函数 (这是桥梁)
    # ============================================================
    def update_vision_ui(self, frame, fps_text,target_info):
        """
        这个函数由 VisionService (子线程) 每帧调用一次。
        Tkinter 不允许子线程直接修改 UI。
        必须使用 root.after(0, func) 将任务扔回主线程执行。
        """

        # ========================================================
        # 1. 自动追踪逻辑 (放在这里，保证就算 UI 卡顿掉帧，追踪也不会停！)
        # ========================================================
        if not self.gimbal_override_enabled and target_info is not None:
            cx, cy, frame_w, frame_h = target_info
            
            error_x = cx - (frame_w / 2.0)
            error_y = cy - (frame_h / 2.0)
            
            # 死区保护
            if abs(error_x) < 30: error_x = 0
            if abs(error_y) < 30: error_y = 0
            
            Kp_pan = 0.01
            Kp_tilt = 0.01
            
            # 计算新角度
            self.current_pan -= error_x * Kp_pan
            self.current_tilt += error_y * Kp_tilt
            
            # 限制范围
            self.current_pan = max(0, min(180, self.current_pan))
            self.current_tilt = max(0, min(150, self.current_tilt))
            
            # 立即发送 UDP 控制硬件 (网络发送很快，不影响子线程)
            self.send_gimbal_udp(int(self.current_pan), int(self.current_tilt))


        if self.view:
            # 2. 核心逻辑：如果当前界面正在画上一帧，直接丢弃这一帧，不要去排队！
            if self.is_drawing:
                return 
        # 上锁
        self.is_drawing = True
        # 发送任务给主线程
        self.root.after(0, lambda: self._start_drawing(frame, fps_text))


    def _start_drawing(self, frame, fps_text):
        try:
            # 3. 执行真正的绘图
            self.view.update_video_frame(frame, fps_text)
        finally:
            # 4. 无论如何，画完了解锁，允许下一帧进来
            self.is_drawing = False


    # ============================================================
    #  心跳循环：控制器的“发动机”，处理定时任务
    # ============================================================
    def heartbeat_loop(self):
        # 如果用户没有用鼠标拖动摇杆 1，则检查键盘是否有输入
        if not self.joy1_dragging:
            # 如果 WASD 任意一个键被按下，则根据按键计算移动数值
            if any(self.keys_move.values()):
                self.calc_speed_from_keys()
            else:
                # 如果没有按键且没有拖动，且当前速度不为0，则可以在此处添加减速停止逻辑
                if self.val_m != 0 or self.val_t != 0:
                     pass 

        # 检查当前机器人是否处于“活动状态”
        # 满足以下任意条件：键盘在动、摇杆在拖、或者数值尚未归零
        is_active = (
            any(self.keys_move.values()) or 
            any(self.keys_pose.values()) or 
            self.val_m != 0 or 
            self.val_t != 0 or
            self.joy1_dragging or 
            self.joy2_dragging
        )

        # 如果处于活动状态，则调用发包函数向硬件发送数据
        if is_active:
            self.send_update_packet(force=True)
        
        # 设定 50 毫秒后再次调用自身，形成无限循环
        self.root.after(50, self.heartbeat_loop)

    # 根据键盘按键状态计算摇杆偏移和速度值
    def calc_speed_from_keys(self):
        tx, ty = 0, 0 # 初始化临时偏移量
        r = DIMS["joy_radius"] # 获取摇杆的最大移动半径
        
        # 根据 WASD 计算 Y 轴和 X 轴的偏移强度（此处系数控制灵敏度）
        if self.keys_move['w']: ty -= r * 0.2 
        if self.keys_move['s']: ty += r * 0.2
        if self.keys_move['a']: tx -= r * 1.0
        if self.keys_move['d']: tx += r * 1.0
        
        # 使用勾股定理计算当前偏移的距离
        dist = math.sqrt(tx*tx + ty*ty)
        # 如果偏移超出了摇杆圆圈半径，则进行等a比例缩放（限幅）
        if dist > r:
            tx = tx * r / dist
            ty = ty * r / dist

        # 获取摇杆 UI 的中心点坐标
        c = DIMS["joy_size"] // 2
        # 更新界面上摇杆球（Knob）的位置
        self.view.joy1.update_position(c + tx, c + ty)

        # 将坐标偏移映射为实际的控制参数（速度和转向）
        self.val_m = int(-ty / r * PARAMS["max_move"])
        self.val_t = int(-tx / r * PARAMS["max_move"])

    # ============================================================
    #  其余部分：逻辑绑定与事件响应
    # ============================================================

    def bind_events(self):
        # 绑定 UI 按钮功能
        self.view.btn_scan.config(command=self.refresh_ports) # 扫描串口按钮
        self.view.btn_connect.config(command=lambda: self.toggle_connect("serial")) # 串口连接按钮
        self.view.btn_tcp_connect.config(command=lambda: self.toggle_connect("tcp")) # 网络连接按钮
        
        # 绑定键盘全局事件：按下与释放
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        
        # 绑定机械零点输入框的回车确认事件
        self.view.entry_zero.bind("<Return>", self.on_zero_confirm)
        # 绑定微调按钮逻辑（调整零点偏置）
        self.view.btn_zero_up.command = lambda: self.adjust_zero(-0.1)
        self.view.btn_zero_down.command = lambda: self.adjust_zero(0.1)
        
        # 绑定虚拟摇杆 1 的鼠标交互（拖动、释放、点击）
        self.view.joy1.tag_bind(self.view.joy1.knob, "<B1-Motion>", self.on_drag_joy1)
        self.view.joy1.tag_bind(self.view.joy1.knob, "<ButtonRelease-1>", self.on_release_joy1)
        self.view.joy1.tag_bind(self.view.joy1.knob, "<Button-1>", lambda e: setattr(self, 'joy1_dragging', True))

        # 绑定虚拟摇杆 2 的鼠标交互
        self.view.joy2.tag_bind(self.view.joy2.knob, "<B1-Motion>", self.on_drag_joy2)
        self.view.joy2.tag_bind(self.view.joy2.knob, "<ButtonRelease-1>", self.on_release_joy2)



        # === 新增：云台摇杆 (joy_gimbal) 事件绑定 ===
        
        # 1. 绑定拖动事件：计算角度并发送 UDP
        # tag_bind 绑定到 knob (摇杆头) 上，这样只有拖动圆点才生效
        self.view.joy_gimbal.tag_bind(self.view.joy_gimbal.knob, "<B1-Motion>", self.on_gimbal_drag)
        
        # 2. 绑定松开事件：自动回中
        self.view.joy_gimbal.tag_bind(self.view.joy_gimbal.knob, "<ButtonRelease-1>", self.on_gimbal_release)
        
        # 3. 绑定点击事件：(可选) 用于标记正在交互状态，防止和其他逻辑冲突
        self.view.joy_gimbal.tag_bind(self.view.joy_gimbal.knob, "<Button-1>", lambda e: setattr(self, 'gimbal_active', True))

        # 4.绑定云台按钮点击事件
        self.view.btn_gimbal_override.config(command=self.toggle_gimbal_override)

      


    # 构建并发送数据包函数
    def send_update_packet(self, force=False):
        now = time.time()
        # 满足强制发送条件，或者距离上次发送已超过 50ms（限流）
        if force or (now - self.last_send_time > 0.05):
            m_int = int(self.val_m)
            t_int = int(self.val_t)
            # 拼接通信协议字符串，格式如：#速度,转向,零点,高度,翻滚\r\n
            cmd_str = f"#{m_int},{t_int},{self.val_zero:.2f},{self.val_h:.1f},{self.val_r:.2f}\r\n"
            # 通过底层服务发送字符串
            self.comms.send(cmd_str)
            self.last_send_time = now

            # 同步更新 UI 界面上的数值标签，显示当前各参数状态
            self.view.lbl_speed.config(text=f"{self.val_m:+04d}")
            self.view.lbl_turn.config(text=f"{self.val_t:+04d}")
            self.view.lbl_r.config(text=f"{self.val_r:.1f}")
            self.view.lbl_h.config(text=f"{self.val_h:.1f}")

    # 处理键盘按下事件
    def on_key_press(self, event):
        key = event.keysym.lower() # 获取按下的键名（转小写）
        
        # 1. 如果是移动键 (WASD)
        if key in self.keys_move:
            self.keys_move[key] = True
            
        # 2. 如果是姿态调整键 (方向键)
        elif event.keysym in self.keys_pose:
            k = event.keysym
            if not self.keys_pose[k]: # 防止按住按键导致的长按触发重复计算
                self.keys_pose[k] = True
                self.step_pose_value(k) # 按步长更新姿态

        # 3. 如果是机械零点快捷键
        elif key == 'i': # i 键调小零点
            self.adjust_zero(-0.5)
        elif key == 'k': # k 键调大零点
            self.adjust_zero(0.5)

    # 处理键盘释放事件
    def on_key_release(self, event):
        key = event.keysym.lower()
        # 释放移动键
        if key in self.keys_move:
            self.keys_move[key] = False
            # 如果所有移动键都释放了，则触发强制停止逻辑
            if not any(self.keys_move.values()):
                self.force_stop_sequence()
        # 释放姿态键
        elif event.keysym in self.keys_pose:
            self.keys_pose[event.keysym] = False

    # 强制停止函数：将速度和转向归零
    def force_stop_sequence(self):
        print("--- [ACTION] STOP ---")
        self.val_m = 0
        self.val_t = 0
        self.send_update_packet(force=True) # 立即发送停止指令
        # 摇杆球回到中心位置
        c = DIMS["joy_size"] // 2
        self.view.joy1.update_position(c, c)




    def toggle_gimbal_override(self):
        """逻辑：切换云台手动控制状态，并更新 UI"""
        self.gimbal_override_enabled = not self.gimbal_override_enabled
        
        if self.gimbal_override_enabled:
            self.view.btn_gimbal_override.config(text="MANUAL: TRUE (ON)")
        else:
            self.view.btn_gimbal_override.config(text="MANUAL: FALSE (OFF)")
            
            # 关闭时，为了安全，强制让界面上的摇杆回中
            c = self.view.joy_gimbal.size // 2
            self.view.joy_gimbal.update_position(c, c)
            # 可选：发送一次回中指令给底层
            # self.send_gimbal_udp(90, 90)





    #云台摇杆绑定了事件，然后事件触发后所执行的函数，用于UDP发送数据
    def on_gimbal_drag(self, event):
        """处理云台摇杆拖动"""
        # 【核心拦截】如果变量为 False，直接退出，摇杆纹丝不动
        if not self.gimbal_override_enabled:
            return 

        self.gimbal_active = True
        
        # 1. 获取对象和参数
        joy = self.view.joy_gimbal
        center = joy.size // 2
        radius = joy.radius # 摇杆活动半径
        
        # 2. 计算鼠标相对于圆心的偏移
        dx = event.x - center
        dy = event.y - center
        distance = (dx**2 + dy**2) ** 0.5
        
        # 3. 圆形限制 (如果拖出圆外，强制拉回圆边缘)
        if distance > radius:
            scale = radius / distance
            dx *= scale
            dy *= scale
            
        # 4. 更新 UI 显示 (让摇杆帽动起来)
        joy.update_position(center + dx, center + dy)
        
        # 5. 计算物理角度 (映射到舵机角度)
        # 假设：
        # Pan (左右): 0度(最右) ~ 180度(最左), 90度居中
        # Tilt (上下): 70度(低头) ~ 110度(抬头), 90度居中
        
        # dx 范围 -radius ~ +radius -> 映射到 +90 ~ -90 偏移
        pan_angle = int(90 - (dx / radius) * 90)
        
        # dy 范围 -radius ~ +radius -> 映射到 +20 ~ -20 偏移 (总摆幅40度)
        tilt_angle = int(90 + (dy / radius) * 90)
        
        # 6. 安全限幅
        pan_angle = max(0, min(180, pan_angle))
        tilt_angle = max(0, min(150, tilt_angle))

        #更新全局舵机角度变量
        self.current_pan = float(pan_angle)
        self.current_tilt = float(tilt_angle)

        
        # 7. 发送 UDP 指令
        self.send_gimbal_udp(self.current_pan, self.current_tilt)

    #云台摇杆绑定了事件，然后事件触发后所执行的函数，用于UDP发送数据
    def on_gimbal_release(self, event):
        """松开摇杆，自动回中"""

        # 【核心拦截】如果变量为 False，直接退出
        if not self.gimbal_override_enabled:
            return 


        self.gimbal_active = False
        
        # UI 回中
        c = self.view.joy_gimbal.size // 2
        self.view.joy_gimbal.update_position(c, c)
        
        # === 【核心同步】物理云台回中，全局变量也必须同步重置为 90 ===
        self.current_pan = 90.0
        self.current_tilt = 90.0

        # 发送回中指令 (90, 90)
        self.send_gimbal_udp(90, 90)

    #云台摇杆绑定了事件，然后事件触发后所执行的函数，用于打印日志
    def send_gimbal_udp(self, p, t):
            """
            发送函数封装：主程序只负责传参数，具体的脏活累活交给 service
            """

            # === 【新增】强制转换为整数，防止 float 类型导致日志或 socket 崩溃 ===
            p = int(p)
            t = int(t)

            # 1. 简单的数据限幅 (业务逻辑留在主程序里比较好)
            p = max(0, min(180, p))
            t = max(0, min(150, t))
            
            # 2. 【核心修改】直接调用对象的 send_angle 方法
            # 不再去碰 socket，也不用管 encode，service 会处理好
            if self.gimbal_service:
                self.gimbal_service.send_angle(p, t)

            # 3. 【新增】在控制台打印日志
            # 为了防止日志刷太快卡死界面，我们加一个简单的限流：
            # 只有当 current_time - last_log_time > 0.1秒 时才打印
            
            current_time = time.time()
            # 如果 self 里没有 last_gimbal_log_time 这个变量，先初始化它
            if not hasattr(self, 'last_gimbal_log_time'):
                self.last_gimbal_log_time = 0

            # 每 0.1 秒打印一次 (频率 10Hz)
            if current_time - self.last_gimbal_log_time > 0.1:
                # 格式化日志内容：时间 + 数据
                # 例如: [10:25:30] TX_GIMBAL >> P:090 T:090
                time_str = time.strftime("%H:%M:%S", time.localtime())
                log_msg = f"[{time_str}] TX_GIMBAL >> P:{p:03d} T:{t:03d}\n"
                
                # 写入日志窗口 (self.console 是你在 _setup_log_area 定义的)
                self.view.console.insert("end", log_msg)
                
                # 自动滚动到底部 (让最新日志可见)
                self.view.console.see("end")
                
                # 更新上次打印时间
                self.last_gimbal_log_time = current_time







    # 处理摇杆 1 的拖动事件的触发函数的逻辑（鼠标控制）
    def on_drag_joy1(self, event):
        self.joy1_dragging = True
        c, r = DIMS["joy_size"] // 2, DIMS["joy_radius"]
        # 计算鼠标位置相对于中心点的距离
        dx, dy = event.x - c, event.y - c
        dist = math.sqrt(dx*dx + dy*dy)
        # 圆形区域限幅
        if dist > r: dx, dy = dx*r/dist, dy*r/dist
        # 更新 UI 位置
        self.view.joy1.update_position(c + dx, c + dy)
        # 计算对应的移动和转向物理值
        self.val_m = int(-dy/r*PARAMS["max_move"])
        self.val_t = int(-dx/r*PARAMS["max_move"])

    # 摇杆 1 释放：停止移动
    def on_release_joy1(self, event):
        self.joy1_dragging = False
        self.force_stop_sequence()

    # 处理方向键点击时的姿态步进计算
    def step_pose_value(self, key):
        changed = False
        # 处理翻滚角 (Roll)
        if key == 'Left': 
            # 左键增加翻滚角，限制最大值
            self.val_r = min(PARAMS["r_max"], self.val_r + PARAMS["r_step"])
            changed = True
        elif key == 'Right': 
            # 右键减小翻滚角，限制最小值
            self.val_r = max(PARAMS["r_min"], self.val_r - PARAMS["r_step"])
            changed = True
        # 处理高度 (Height)
        elif key == 'Up': 
            # 上键增高
            self.val_h = min(PARAMS["h_max"], self.val_h + PARAMS["h_step"])
            changed = True
        elif key == 'Down': 
            # 下键降低
            self.val_h = max(PARAMS["h_min"], self.val_h - PARAMS["h_step"])
            changed = True
        
        # 如果数值发生了变化，更新界面摇杆 2 的点位并发送数据包
        if changed: 
            self.update_joy2_ui_position()
            self.send_update_packet(force=True)

    # 处理摇杆 2 的拖动事件的触发函数的逻辑（鼠标控制高度和翻滚）
    def on_drag_joy2(self, event):
        self.joy2_dragging = True
        c, r = DIMS["joy_size"] // 2, DIMS["joy_radius"]
        dx, dy = event.x - c, event.y - c
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > r: dx, dy = dx*r/dist, dy*r/dist
        
        # 将摇杆 X 轴映射到翻滚角
        self.val_r = (-dx/r) * PARAMS["r_max"]
        # 将摇杆 Y 轴映射到高度（相对于默认高度的偏移）
        self.val_h = PARAMS["h_default"] - (dy/r)*(PARAMS["h_max"]-PARAMS["h_default"])
        
        self.update_joy2_ui_position()

    # 摇杆 2 释放时仅更新状态
    def on_release_joy2(self, event): 
        self.joy2_dragging = False

    # 根据当前的物理值 (r, h) 反向更新摇杆 2 在界面上的坐标
    def update_joy2_ui_position(self):
        r, c = DIMS["joy_radius"], DIMS["joy_size"] // 2
        # 计算相对于中心点的像素偏移量
        dx = -(self.val_r / PARAMS["r_max"]) * r
        dy = -((self.val_h - PARAMS["h_default"]) / (PARAMS["h_max"] - PARAMS["h_default"])) * r
        self.view.joy2.update_position(c + dx, c + dy)

    # 调整机械零点偏置
    def adjust_zero(self, delta):
        self.val_zero += delta
        # 更新输入框显示的文字
        self.view.entry_zero.delete(0, tk.END)
        self.view.entry_zero.insert(0, f"{self.val_zero:.1f}")
        # 立即发送更新数据包
        self.send_update_packet(force=True)

    # 当在零点输入框按回车时的处理
    def on_zero_confirm(self, event):
        try:
            content = self.view.entry_zero.get().strip()
            if content:
                self.val_zero = float(content)
                self.send_update_packet(force=True)
                # 失去焦点，回到主窗口，方便继续使用键盘控制
                self.root.focus_set()
        except ValueError:
            pass

    # 将日志消息显示在 UI 界面上
    def log_msg(self, text):
        # 获取当前时间
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        # 使用 after(0, ...) 确保在主线程（GUI 线程）更新 UI
        self.root.after(0, lambda: self.view.log(f"[{ts}] {text}"))

    # 刷新并列出系统当前的串口列表
    def refresh_ports(self):
        ports = self.comms.get_ports()
        self.view.port_combo['values'] = ports
        if ports: self.view.port_combo.current(0)

    # 切换连接状态（连接/断开）
    def toggle_connect(self, mode):
        # 如果当前未连接，则尝试建立连接
        if not self.comms.is_connected:
            if mode == "serial":
                # 串口模式：获取下拉框选中的端口
                target = self.view.port_combo.get().strip()
                active_btn = self.view.btn_connect
                success_text = "CONNECTED"
            else:
                # 网络模式：获取 IP 和端口
                ip = self.view.entry_ip.get().strip()
                port = self.view.entry_port.get().strip()

                #存储ip地址和端口
                target = f"{ip}:{port}"  

                active_btn = self.view.btn_tcp_connect
                success_text = "LINKED"

            # 如果没有输入地址则返回
            if not target or target == ":": return
            


            # 调用底层通信接口连接
            success, msg = self.comms.connect(target)



            if success:
                # 连接成功：改变按钮颜色（变红）和文字
                active_btn.config(text=success_text, bootstyle="danger")
                self.log_msg(f"[SYS] >> {msg}")
                self.root.focus_set() # 窗口获得焦点以便捕获按键
        else:
            # 如果当前已连接，则断开连接
            self.comms.disconnect()
            # 恢复按钮外观
            self.view.btn_connect.config(text="CONNECT", bootstyle="success-outline")
            self.view.btn_tcp_connect.config(text="LINK", bootstyle="success-outline")
            self.log_msg("[SYS] >> DISCONNECTED")


# 程序入口
if __name__ == "__main__":
    app = Controller()