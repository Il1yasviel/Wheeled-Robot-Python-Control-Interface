# -*- coding: utf-8 -*-
import math
import time
import datetime
import tkinter as tk
import ttkbootstrap as ttk
import os

# 从自定义模块导入
from config import COLORS, DIMS, PARAMS, UDP_CONFIG
from view import MainView
from comms import HybridService, GimbalUDPService
from vision_service import VisionService 
from sensor_service import SensorService 
from input_handler import InputHandler  # 新增导入
from ai_bridge_service import AIBridgeService

class Controller:
    def __init__(self):
        # ==========================================
        # 1. 核心 UI 与 服务初始化
        # ==========================================
        self.root = ttk.Window(themename="cyborg")
        self.view = MainView(self.root, self.close_app)
        self.comms = HybridService(self.log_msg)
        self.gimbal_service = GimbalUDPService(UDP_CONFIG["RK3506_ip"], UDP_CONFIG["RK3506_UDP_port"])

        # ==========================================
        # 2. 状态变量定义
        # ==========================================
        # --- 云台控制相关变量 ---
        self.gimbal_override_enabled = False  # 云台手动控制是否开启
        self.current_pan = 90                 # 左右舵机全局角度
        self.current_tilt = 90                # 上下舵机全局角度
        self.val_pan = 90                     # 左右舵机默认角度
        self.val_tilt = 90                    # 上下舵机默认角度
        self.joy_gimbal_dragging = False      # 云台摇杆拖动标志
        self.gimbal_active = False            # 云台交互状态
        self.last_gimbal_log_time = 0         # 云台日志限流时间戳

        # --- 初始化变量 ---
        self.val_yh = 0 # 用于存储 Y/H 轴的数值

        # --- 底盘与姿态运动变量 ---
        self.val_m = 0                        # 前进/后退速度 (Movement)
        self.val_t = 0                        # 左右转向值 (Turnment)
        self.val_r = 0.0                      # 机身翻滚角 (Roll)
        self.val_h = PARAMS["h_default"]      # 机身高度 (Height)
        
        # --- 零点与按键状态 ---
        try:
            z_str = self.view.entry_zero.get().strip()
            self.val_zero = float(z_str) if z_str else 0.0
        except ValueError:
            self.val_zero = 0.0

        self.keys_move = {'w': False, 's': False, 'a': False, 'd': False}
        self.keys_pose = {'Up': False, 'Down': False, 'Left': False, 'Right': False}
        
        self.joy1_dragging = False            # 左侧虚拟摇杆拖动标志
        self.joy2_dragging = False            # 右侧虚拟摇杆拖动标志
        self.is_drawing = False               # 视觉绘图锁，防止UI卡顿
        self.last_send_time = 0               # 上次发送控制包的时间

        # ==========================================
        # 3. 启动准备与线程绑定
        # ==========================================
        # 实例化输入处理器，并把 self 传进去
        self.input_handler = InputHandler(self)

        # ==========================================
        # ★ 新增：实例化 AI 桥接服务
        # 把更新UI聊天框的函数、保存音频的函数 传递进去
        # ==========================================
        self.ai_bridge = AIBridgeService(
            ui_chat_callback=self.update_chat_ui, 
            save_audio_callback=self.save_received_audio
        )

        self.bind_events()
        self.refresh_ports()
        self._start_background_threads()
        
        # 启动心跳循环
        self.heartbeat_loop()
        # 进入主循环
        self.root.mainloop()

    # ============================================================
    # ★ 生命周期与后台线程管理
    # ============================================================
    def _start_background_threads(self):
        """初始化并启动所有后台数据采集与视觉线程"""
        # 1. 启动视觉检测线程
        video_url = "http://192.168.10.114:8080/?action=stream" 
        self.vision_thread = VisionService(video_url, self.update_vision_ui)
        self.vision_thread.daemon = True 
        self.vision_thread.start()

        # 2. 启动传感器数据线程
        target_ip = UDP_CONFIG["RK3506_ip"] 
        target_port = UDP_CONFIG["RK3506_sensor_port"]
        self.sensor_thread = SensorService(target_ip, target_port, self.update_sensor_ui)
        self.sensor_thread.daemon = True
        self.sensor_thread.start()

    def close_app(self):
        """统一的关闭程序函数"""
        print("--- Closing App & Stopping Threads ---")
        
        if hasattr(self, 'vision_thread'):
            try:
                self.vision_thread.stop()
                print("Vision thread stopped.")
            except Exception as e:
                print(f"Error stopping vision: {e}")
        
        if hasattr(self, 'sensor_thread'):
            try:
                self.sensor_thread.stop()
                print("Sensor thread stopped.")
            except Exception as e:
                print(f"Error stopping sensor: {e}")

        if hasattr(self, 'comms'):
            self.comms.disconnect()
            print("Comms disconnected.")

        try:
            self.root.destroy()
            print("Window destroyed.")
        except Exception as e:
            print(f"Error destroying window: {e}")

    # ============================================================
    # ★ 传感器与视觉 UI 更新回调
    # ============================================================
    def update_sensor_ui(self, text):
        """由 SensorService 子线程调用，切回主线程更新 UI"""
        self.root.after(0, lambda: self.view.update_env_data(text))

    def update_vision_ui(self, frame, fps_text, target_info):
        """由 VisionService 子线程调用，处理追踪逻辑并绘制图像"""
        # 1. 自动追踪逻辑 (脱离绘图锁，确保追踪不卡顿)
        if not self.gimbal_override_enabled and target_info is not None:
            cx, cy, frame_w, frame_h = target_info
            
            error_x = cx - (frame_w / 2.0)
            error_y = cy - (frame_h / 2.0)
            
            # 死区保护
            if abs(error_x) < 30: error_x = 0
            if abs(error_y) < 30: error_y = 0
            
            Kp_pan, Kp_tilt = 0.01, 0.01
            
            self.current_pan -= error_x * Kp_pan
            self.current_tilt += error_y * Kp_tilt
            
            self.current_pan = max(0, min(180, self.current_pan))
            self.current_tilt = max(0, min(150, self.current_tilt))
            
            self.send_gimbal_udp(int(self.current_pan), int(self.current_tilt))

        # 2. 图像绘制逻辑
        if self.view:
            if self.is_drawing:
                return 
            self.is_drawing = True
            self.root.after(0, lambda: self._start_drawing(frame, fps_text))

    def _start_drawing(self, frame, fps_text):
        try:
            self.view.update_video_frame(frame, fps_text)
        finally:
            self.is_drawing = False

    # ============================================================
    # ★ 核心通信与控制心跳
    # ============================================================
    def heartbeat_loop(self):
        """控制器的‘发动机’：现在它是无条件的，每 50ms 必然发送一次数据包"""
        
        # 1. 自动处理控制逻辑：计算当前应该发送什么数值
        if not self.joy1_dragging:
            # 如果没有在拖动摇杆
            if any(self.keys_move.values()):
                # 如果有键盘按键，则计算键盘控制的速度
                self.input_handler.calc_speed_from_keys()
            else:
                # 【关键点】既没按键盘也没拉摇杆 -> 强制数值回正为 0
                # 这样发出的包里速度就是 0，机器人会立刻停止
                self.val_m = 0
                self.val_t = 0
                # 如果你的 val_yh 也是一种瞬时速度，也可以在这里归零
                # self.val_yh = 0

        # 2. 【核心修改】删掉 is_active 逻辑，直接“暴力”发送
        # 不管现在的状态是移动还是停止，只要循环在跑，就往外发包
        self.send_update_packet(force=True)

        # 3. (建议) 把云台也带上，实现全系统状态同步
        # 即使云台没动，持续发送当前角度也能防止丢包导致的“位置不到位”
        if self.gimbal_override_enabled:
            self.send_gimbal_udp(self.current_pan, self.current_tilt)
        
        # 4. 维持 20Hz 的频率 (50ms 一次)
        self.root.after(50, self.heartbeat_loop)

    def send_update_packet(self, force=False):
        """构建并向底盘发送控制数据包"""
        now = time.time()
        if force or (now - self.last_send_time > 0.05):
            m_int = int(self.val_m)
            t_int = int(self.val_t)
            # 【核心修复】：你需要增加下面这一行，把 self.val_yh 转成整数存进 yh_int
            yh_int = int(self.val_yh) 
            # 假设你修改了单片机的接收协议，在最后增加了一个 yh 字段
            # 如果不改协议，你可以根据需要决定将这个值合并到 m 还是单独处理
            cmd_str = f"#{m_int},{t_int},{self.val_zero:.2f},{self.val_h:.1f},{self.val_r:.2f},{yh_int}\r\n"
            
            self.comms.send(cmd_str)
            self.last_send_time = now

            self.view.lbl_speed.config(text=f"{self.val_m:+04d}")
            self.view.lbl_turn.config(text=f"{self.val_t:+04d}")
            self.view.lbl_r.config(text=f"{self.val_r:.1f}")
            self.view.lbl_h.config(text=f"{self.val_h:.1f}")

    def send_gimbal_udp(self, p, t):
        """向云台发送 UDP 控制指令"""
        p, t = int(p), int(t)
        p = max(0, min(180, p))
        t = max(0, min(150, t))
        
        if self.gimbal_service:
            self.gimbal_service.send_angle(p, t)

        current_time = time.time()
        if current_time - self.last_gimbal_log_time > 0.1:
            time_str = time.strftime("%H:%M:%S", time.localtime())
            log_msg = f"[{time_str}] TX_GIMBAL >> P:{p:03d} T:{t:03d}\n"
            
            self.view.console.insert("end", log_msg)
            self.view.console.see("end")
            self.last_gimbal_log_time = current_time

    def log_msg(self, text):
        """
        所有来自串口、UDP 或系统的原始调试消息，都会流经这里。
        """
        # 获取当前时间戳
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 1. 如果你想针对特定数据（如速度）做特殊格式化，但依然打印在左侧：
        if "CAR_SPD:" in text:
            try:
                speed_val = text.split("CAR_SPD:")[1].strip()
                # 依然调用 self.view.log，这样它就会出现在左侧控制台
                self.root.after(0, lambda: self.view.log(f"[{ts}] [TELEMETRY] Speed: {speed_val} mm/s"))
                return 
            except:
                pass

        # 2. 默认逻辑：直接将所有原始信息打印在左侧控制台
        self.root.after(0, lambda: self.view.log(f"[{ts}] {text}"))

    # ============================================================
    # ★ 连接管理
    # ============================================================
    def refresh_ports(self):
        """刷新串口列表"""
        ports = self.comms.get_ports()
        self.view.port_combo['values'] = ports
        if ports: self.view.port_combo.current(0)

    def toggle_connect(self, mode):
        """切换连接状态（串口/TCP网络）"""
        if not self.comms.is_connected:
            if mode == "serial":
                target = self.view.port_combo.get().strip()
                active_btn = self.view.btn_connect
                success_text = "CONNECTED"
            else:
                ip = self.view.entry_ip.get().strip()
                port = self.view.entry_port.get().strip()
                target = f"{ip}:{port}"  
                active_btn = self.view.btn_tcp_connect
                success_text = "LINKED"

            if not target or target == ":": return
            
            success, msg = self.comms.connect(target)

            if success:
                active_btn.config(text=success_text, bootstyle="danger")
                self.log_msg(f"[SYS] >> {msg}")
                self.root.focus_set()
        else:
            self.comms.disconnect()
            self.view.btn_connect.config(text="CONNECT", bootstyle="success-outline")
            self.view.btn_tcp_connect.config(text="LINK", bootstyle="success-outline")
            self.log_msg("[SYS] >> DISCONNECTED")

    # ============================================================
    # ★ UI 绑定与系统事件处理
    # ============================================================
    def bind_events(self):
            """集中绑定所有的UI事件和快捷键"""
            # ==========================================
            # 1. 保留的部分：只管普通的 UI 按钮和输入框
            # ==========================================
            self.view.btn_scan.config(command=self.refresh_ports)
            self.view.btn_connect.config(command=lambda: self.toggle_connect("serial"))
            self.view.btn_tcp_connect.config(command=lambda: self.toggle_connect("tcp"))
            
            # 零点微调与确认
            self.view.entry_zero.bind("<Return>", self.on_zero_confirm)
            self.view.btn_zero_up.command = lambda: self.adjust_zero(-0.1)
            self.view.btn_zero_down.command = lambda: self.adjust_zero(0.1)
            
            # 云台手动模式切换按钮
            self.view.btn_gimbal_override.config(command=self.toggle_gimbal_override)

            # ==========================================
            # 2. 修改的部分：把键盘和摇杆的脏活累活全丢给 input_handler
            # ==========================================
            # 这一行代码，等同于旧代码里那十几行 joy.tag_bind 和 root.bind
            self.input_handler.bind_all()



    # ============================================================
    # ★ 云台控制与零点微调
    # ============================================================
    def toggle_gimbal_override(self):
        self.gimbal_override_enabled = not self.gimbal_override_enabled
        
        if self.gimbal_override_enabled:
            self.view.btn_gimbal_override.config(text="MANUAL: TRUE (ON)")
        else:
            self.view.btn_gimbal_override.config(text="MANUAL: FALSE (OFF)")
            c = self.view.joy_gimbal.size // 2
            self.view.joy_gimbal.update_position(c, c)



    def adjust_zero(self, delta):
        self.val_zero += delta
        self.view.entry_zero.delete(0, tk.END)
        self.view.entry_zero.insert(0, f"{self.val_zero:.1f}")
        self.send_update_packet(force=True)

    def on_zero_confirm(self, event):
        try:
            content = self.view.entry_zero.get().strip()
            if content:
                self.val_zero = float(content)
                self.send_update_packet(force=True)
                self.root.focus_set()
        except ValueError:
            pass


    # ============================================================
    # ★ 聊天记录与 AI 交互控制方法
    # ============================================================
    def init_storage_dirs(self):
        """初始化本地存储目录"""
        self.chat_log_dir = "chat_logs"
        self.audio_save_dir = "received_audios"
        
        # 确保目录存在
        os.makedirs(self.chat_log_dir, exist_ok=True)
        os.makedirs(self.audio_save_dir, exist_ok=True)
        
        # 每天生成一个新的 txt 文件用来存聊天记录
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        self.current_chat_file = os.path.join(self.chat_log_dir, f"chat_history_{date_str}.txt")

    def update_chat_ui(self, role, text, end=""):
        """
        供 AI Bridge 调用的回调函数：将 AI 或 User 的文字画在界面上，并保存到本地
        """
        # 1. 强制在主线程更新 UI 界面
        self.root.after(0, lambda: self.view.append_chat(role, text, end))
        
        # 2. 悄悄写进本地日志文件 (追加模式)
        try:
            with open(self.current_chat_file, "a", encoding="utf-8") as f:
                f.write(text + end)
        except Exception as e:
            print(f"聊天记录保存失败: {e}")

    def save_received_audio(self, audio_bytes):
        """
        供 AI Bridge 调用的回调函数：保存接收到的 AI 语音包
        """
        try:
            # 用时间戳保证文件名唯一，防止覆盖
            filename = f"ai_reply_{int(time.time() * 1000)}.wav"
            filepath = os.path.join(self.audio_save_dir, filename)
            
            with open(filepath, "wb") as f:
                f.write(audio_bytes)
                
            # 在 UI 里面用灰色字体打个小提示，告诉用户收到了语音包
            self.update_chat_ui("System", f"[System] 收到语音数据，已保存至: {filename}\n", "")
        except Exception as e:
            print(f"音频保存失败: {e}")        


# 程序入口
if __name__ == "__main__":
    app = Controller()