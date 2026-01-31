# -*- coding: utf-8 -*-
import tkinter as tk
import ttkbootstrap as ttk
import math
import time
import datetime
from config import COLORS, DIMS, PARAMS
from view import MainView
from comms import SerialService
from comms import TCPService # 确保导入的是 TCPService
from comms import HybridService

class Controller:
    def __init__(self):
        self.root = ttk.Window(themename="cyborg")
        self.view = MainView(self.root, self.close_app)
        self.comms = HybridService(self.log_msg)
        # --- 状态变量 ---
        self.keys_move = {'w': False, 's': False, 'a': False, 'd': False}
        self.keys_pose = {'Up': False, 'Down': False, 'Left': False, 'Right': False}
        self.pose_key_timers = {}
        self.last_pose_action_time = time.time()
        
        self.val_r = 0.0
        self.val_h = PARAMS["h_default"]
        self.joy2_dragging = False
        
        self.last_send_time = 0
        self.last_sent_m = None
        self.last_sent_t = None

        # --- 初始化绑定 ---
        self.bind_events()
        self.refresh_ports()
        
        # --- 启动循环 ---
        self.log_msg("[SYS] SYSTEM INITIALIZED...")
        self.check_pose_keys_loop()
        self.auto_return_loop()
        
        self.root.mainloop()

    def bind_events(self):
            """统一管理所有交互事件"""
            # --- 1. 串口与系统按钮 ---
            self.view.btn_scan.config(command=self.refresh_ports)
            
            # 串口按钮：传入 "serial"
            self.view.btn_connect.config(command=lambda: self.toggle_connect("serial"))

            # TCP 按钮：传入 "tcp"
            self.view.btn_tcp_connect.config(command=lambda: self.toggle_connect("tcp"))
            
            # --- 2. 移动与姿态 (全局监听 WASD 和 方向键) ---
            self.root.bind("<KeyPress>", self.on_key_press)
            self.root.bind("<KeyRelease>", self.on_key_release)

            # --- 3. 机械零点快捷键 (I/K) ---
            # 使用 lambda _: 忽略掉 Tkinter 传来的 event 参数
            self.root.bind("i", lambda _: self.adjust_zero(-0.5)) 
            self.root.bind("k", lambda _: self.adjust_zero(0.5))
            self.root.bind("I", lambda _: self.adjust_zero(-0.5)) 
            self.root.bind("K", lambda _: self.adjust_zero(0.5))

            # --- 4. 机械零点输入框事件 ---
            # 回车确认
            self.view.entry_zero.bind("<Return>", self.on_zero_confirm)
            self.view.entry_zero.bind("<KP_Enter>", self.on_zero_confirm)
            
            # --- 5. 机械零点 UI 按钮 (EvaButton) ---
            self.view.btn_zero_up.command = lambda: self.adjust_zero(-0.5)
            self.view.btn_zero_down.command = lambda: self.adjust_zero(0.5)
            
            # --- 6. 摇杆 1 (移动) 鼠标事件 ---
            self.view.joy1.tag_bind(self.view.joy1.knob, "<B1-Motion>", self.on_drag_joy1)
            self.view.joy1.tag_bind(self.view.joy1.knob, "<ButtonRelease-1>", self.on_release_joy1)
            self.view.joy1.tag_bind(self.view.joy1.knob_center, "<B1-Motion>", self.on_drag_joy1)
            self.view.joy1.tag_bind(self.view.joy1.knob_center, "<ButtonRelease-1>", self.on_release_joy1)
            
            # --- 7. 摇杆 2 (姿态) 鼠标事件 ---
            self.view.joy2.tag_bind(self.view.joy2.knob, "<B1-Motion>", self.on_drag_joy2)
            self.view.joy2.tag_bind(self.view.joy2.knob, "<ButtonRelease-1>", self.on_release_joy2)
            self.view.joy2.tag_bind(self.view.joy2.knob_center, "<B1-Motion>", self.on_drag_joy2)
            self.view.joy2.tag_bind(self.view.joy2.knob_center, "<ButtonRelease-1>", self.on_release_joy2)
            
            # 捕获在摇杆外松开鼠标的情况，确保回中
            self.view.joy2.bind("<ButtonRelease-1>", self.on_release_joy2)

    def close_app(self):
        self.comms.disconnect()
        self.root.destroy()

    def log_msg(self, text):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        # 使用 after 确保在主线程更新 UI
        self.root.after(0, lambda: self.view.log(f"[{timestamp}] {text}"))

    # --- 串口逻辑 ---
    def refresh_ports(self):
        ports = self.comms.get_ports()
        self.view.port_combo['values'] = ports
        if ports: self.view.port_combo.current(0)

    def toggle_connect(self, mode):
        """
        mode: "serial" 或 "tcp"
        """
        # 1. 如果当前没有连接，则尝试连接
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

            print(f"\n--- [BUTTON CLICK] Mode: {mode}, Target: '{target}' ---")

            if not target or target == ":":
                self.log_msg(f"[SYS] >> ERROR: No {mode.upper()} Target")
                return

            # 执行连接
            success, msg = self.comms.connect(target)
            
            if success:
                # 连接成功：设置指定的按钮文字和样式（danger 是红色背景）
                active_btn.config(text=success_text, bootstyle="danger")
                self.log_msg(f"[SYS] >> {msg}")
                self.root.focus_set()
            else:
                self.log_msg(f"[SYS] >> {msg}")
                tk.messagebox.showwarning("Connection Failed", msg)
        
        # 2. 如果当前已经连接，则执行断开
        else:
            print("--- [ACTION] Disconnecting current session... ---")
            self.comms.disconnect()
            
            # 恢复所有按钮到初始状态
            self.view.btn_connect.config(text="CONNECT", bootstyle="success-outline")
            self.view.btn_tcp_connect.config(text="LINK", bootstyle="success-outline")
            
            self.log_msg("[SYS] >> CLOSED")

    def adjust_zero(self, delta):
            """
            调整机械零点逻辑
            """
            # --- 新增：焦点检查 ---
            # 如果当前焦点在输入框上，说明用户正在打字，此时禁用 I/K 快捷键
            if self.root.focus_get() == self.view.entry_zero:
                return

            # 获取当前输入框的内容
            content = self.view.entry_zero.get().strip()
            
            if not content:
                # 如果输入框是空的，给一个初始值 0.0
                current_val = 0.0
            else:
                try:
                    current_val = float(content)
                except ValueError:
                    self.log_msg("[ERR] Invalid Zero Value")
                    return

            # 计算新值
            new_val = current_val + delta
            
            # 更新输入框
            self.view.entry_zero.delete(0, tk.END)
            self.view.entry_zero.insert(0, f"{new_val:.1f}")
            
            # 发送命令
            cmd = f"P7,{new_val:.1f}\r\n"
            self.comms.send(cmd)
            self.log_msg(f"[CMD] Zero Adj -> {cmd.strip()}")


    def on_zero_confirm(self, event):
            """
            当在输入框按回车时触发：发送数据并释放焦点
            """
            content = self.view.entry_zero.get().strip()
            if not content:
                return

            try:
                val = float(content)
                # 1. 发送串口命令
                cmd = f"P7,{val:.1f}\r\n"
                self.comms.send(cmd)
                self.log_msg(f"[CMD] Zero Confirmed -> {cmd.strip()}")
                
                # 2. 【关键】释放焦点
                # 这样按完回车后，光标会退出输入框，WASD 键就能继续控车了
                self.root.focus_set()
                
            except ValueError:
                self.log_msg("[ERR] Invalid Zero Value")



    # --- 移动控制 (Joy1 / WASD) ---
    def on_key_press(self, event):
        key = event.keysym
        if key.lower() in self.keys_move:
            if not self.keys_move[key.lower()]:
                self.keys_move[key.lower()] = True
                self.update_joy1_from_keys()
        elif key in self.keys_pose:
            self.last_pose_action_time = time.time()
            if not self.keys_pose[key]:
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
    #控制前后左右移动
    def update_joy1_from_keys(self):
        target_x, target_y = 0, 0
        radius = DIMS["joy_radius"]
        offset_speed = radius * 0.18   #前进后退幅度
        offset_turn = radius * 0.8

        if self.keys_move['w']: target_y -= offset_speed
        if self.keys_move['s']: target_y += offset_speed
        if self.keys_move['a']: target_x -= offset_turn
        if self.keys_move['d']: target_x += offset_turn

        center = DIMS["joy_size"] // 2
        self.view.joy1.update_position(center + target_x, center + target_y)
        
        speed_val = int(-target_y / radius * PARAMS["max_move"])
        turn_val = int(-target_x / radius * PARAMS["max_move"])
        self.send_move_command(speed_val, turn_val, force=True)

    def on_drag_joy1(self, event):
        center = DIMS["joy_size"] // 2
        radius = DIMS["joy_radius"]
        dx = event.x - center
        dy = event.y - center
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance > radius:
            ratio = radius / distance
            dx *= ratio
            dy *= ratio
            
        self.view.joy1.update_position(center + dx, center + dy)
        speed_val = int(-dy / radius * PARAMS["max_move"])
        turn_val = int(-dx / radius * PARAMS["max_move"])
        self.send_move_command(speed_val, turn_val)

    def on_release_joy1(self, event):
        center = DIMS["joy_size"] // 2
        self.view.joy1.update_position(center, center)
        self.send_move_command(0, 0, force=True)
        self.comms.send("S\r\n")

    def send_move_command(self, m, t, force=False):
        self.view.lbl_speed.config(text=f"{m:+04d}")
        self.view.lbl_turn.config(text=f"{t:+04d}")
        
        current_time = time.time()
        if force or (current_time - self.last_send_time > PARAMS["send_interval"]):
            if force or (m != self.last_sent_m):
                self.comms.send(f"M{m}\r\n")
                self.last_sent_m = m
                time.sleep(0.08) # 避免指令粘连
            if force or (t != self.last_sent_t):
                self.comms.send(f"T{t}\r\n")
                self.last_sent_t = t
            self.last_send_time = time.time()

    # --- 姿态控制 (Joy2 / Arrows) ---
    def step_pose_value(self, key):
        changed = False
        if key == 'Left':
            self.val_r = max(PARAMS["r_min"], self.val_r - PARAMS["r_step"])
            changed = True
        elif key == 'Right':
            self.val_r = min(PARAMS["r_max"], self.val_r + PARAMS["r_step"])
            changed = True
        elif key == 'Up':
            self.val_h = min(PARAMS["h_max"], self.val_h + PARAMS["h_step"])
            changed = True
        elif key == 'Down':
            self.val_h = max(PARAMS["h_min"], self.val_h - PARAMS["h_step"])
            changed = True
            
        if changed:
            self.update_joy2_ui()
            self.send_pose_command()

    def check_pose_keys_loop(self):
        current_time = time.time()
        for key, start_time in list(self.pose_key_timers.items()):
            if current_time - start_time >= 0.1:
                self.step_pose_value(key)
                self.pose_key_timers[key] = current_time
                self.last_pose_action_time = current_time
        self.root.after(20, self.check_pose_keys_loop)

    def on_drag_joy2(self, event):
        self.joy2_dragging = True
        self.last_pose_action_time = time.time()
        
        center = DIMS["joy_size"] // 2
        radius = DIMS["joy_radius"]
        dx = event.x - center
        dy = event.y - center
        
        distance = math.sqrt(dx*dx + dy*dy)
        if distance > radius:
            ratio = radius / distance
            dx *= ratio
            dy *= ratio
            
        pct_x = dx / radius
        pct_y = dy / radius
        
        self.val_r = pct_x * PARAMS["r_max"]
        delta_h = PARAMS["h_max"] - PARAMS["h_default"]
        self.val_h = PARAMS["h_default"] - (pct_y * delta_h)
        
        # Clamp values
        self.val_r = max(PARAMS["r_min"], min(PARAMS["r_max"], self.val_r))
        self.val_h = max(PARAMS["h_min"], min(PARAMS["h_max"], self.val_h))
        
        self.update_joy2_ui()
        self.send_pose_command()

    def on_release_joy2(self, event):
        self.joy2_dragging = False
        self.last_pose_action_time = time.time()

    def update_joy2_ui(self):
        # 更新数据标签
        self.view.lbl_r.config(text=f"{self.val_r:.1f}")
        self.view.lbl_h.config(text=f"{self.val_h:.1f}")
        
        # 反向计算摇杆位置
        radius = DIMS["joy_radius"]
        center = DIMS["joy_size"] // 2
        
        ratio_r = self.val_r / PARAMS["r_max"]
        dx = ratio_r * radius
        
        delta = self.val_h - PARAMS["h_default"]
        ratio_h = - (delta / (PARAMS["h_max"] - PARAMS["h_default"]))
        dy = ratio_h * radius
        
        self.view.joy2.update_position(center + dx, center + dy)

    def send_pose_command(self):
        self.comms.send(f"R{self.val_r:.2f}\r\n")
        time.sleep(0.02)
        self.comms.send(f"h{self.val_h:.2f},{self.val_h:.2f}\r\n")

    def auto_return_loop(self):
        current_time = time.time()
        if not any(self.keys_pose.values()) and not self.joy2_dragging:
            if current_time - self.last_pose_action_time > 1.0:
                if not hasattr(self, 'last_auto_return_tick'):
                    self.last_auto_return_tick = current_time
                
                if current_time - self.last_auto_return_tick >= 0.5:
                    changed = False
                    # R 回中
                    if abs(self.val_r) > 0.1:
                        self.val_r += -PARAMS["r_step"] if self.val_r > 0 else PARAMS["r_step"]
                        if abs(self.val_r) < PARAMS["r_step"]: self.val_r = 0.0
                        changed = True
                    
                    # H 回中
                    h_def = PARAMS["h_default"]
                    if abs(self.val_h - h_def) > 0.1:
                        self.val_h += -PARAMS["h_step"] if self.val_h > h_def else PARAMS["h_step"]
                        if abs(self.val_h - h_def) < PARAMS["h_step"]: self.val_h = h_def
                        changed = True
                    
                    if changed:
                        self.update_joy2_ui()
                        self.send_pose_command()
                    self.last_auto_return_tick = current_time
        else:
            self.last_auto_return_tick = time.time()
        
        self.root.after(100, self.auto_return_loop)

if __name__ == "__main__":
    app = Controller()