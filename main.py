# -*- coding: utf-8 -*-
import tkinter as tk
import ttkbootstrap as ttk
import math, time, datetime
from config import COLORS, DIMS, PARAMS
from view import MainView
from comms import HybridService

class Controller:
    def __init__(self):
        self.root = ttk.Window(themename="cyborg")
        self.view = MainView(self.root, self.close_app)
        self.comms = HybridService(self.log_msg)
        
        # --- 运动状态变量 (核心状态) ---
        self.val_m = 0      # 速度 (Movement)
        self.val_t = 0      # 转向 (Turnment)
        self.val_r = 0.0    # 翻滚角 (Roll)
        self.val_h = PARAMS["h_default"] # 高度 (Height)
        self.val_zero = 0.0 # 机械零点 (Mechanical Zero)

        # 按键状态记录
        self.keys_move = {'w': False, 's': False, 'a': False, 'd': False}
        self.keys_pose = {'Up': False, 'Down': False, 'Left': False, 'Right': False}
        
        self.joy2_dragging = False
        self.joy1_dragging = False 
        
        # 发送频率控制
        self.last_send_time = 0
        
        # 初始化 UI 默认值
        try:
            z_str = self.view.entry_zero.get().strip()
            self.val_zero = float(z_str) if z_str else 0.0
        except:
            self.val_zero = 0.0

        self.bind_events()
        self.refresh_ports()

        # 启动心跳循环 (每 50ms 运行一次)
        self.heartbeat_loop()

        self.root.mainloop()

    # ============================================================
    #  心跳循环
    # ============================================================
    def heartbeat_loop(self):
        # 如果摇杆正在被鼠标拖动，则不处理键盘逻辑
        if not self.joy1_dragging:
            if any(self.keys_move.values()):
                self.calc_speed_from_keys()
            else:
                if self.val_m != 0 or self.val_t != 0:
                     pass 

        # 检查是否需要连续发送
        is_active = (
            any(self.keys_move.values()) or 
            any(self.keys_pose.values()) or 
            self.val_m != 0 or 
            self.val_t != 0 or
            self.joy1_dragging or 
            self.joy2_dragging
        )

        if is_active:
            self.send_update_packet(force=True)
        
        self.root.after(50, self.heartbeat_loop)

    def calc_speed_from_keys(self):
        tx, ty = 0, 0
        r = DIMS["joy_radius"]
        
        if self.keys_move['w']: ty -= r * 0.2 
        if self.keys_move['s']: ty += r * 0.2
        if self.keys_move['a']: tx -= r * 1.0
        if self.keys_move['d']: tx += r * 1.0
        
        dist = math.sqrt(tx*tx + ty*ty)
        if dist > r:
            tx = tx * r / dist
            ty = ty * r / dist

        c = DIMS["joy_size"] // 2
        self.view.joy1.update_position(c + tx, c + ty)

        self.val_m = int(-ty / r * PARAMS["max_move"])
        self.val_t = int(-tx / r * PARAMS["max_move"])

    # ============================================================
    #  其余部分
    # ============================================================

    def bind_events(self):
        self.view.btn_scan.config(command=self.refresh_ports)
        self.view.btn_connect.config(command=lambda: self.toggle_connect("serial"))
        self.view.btn_tcp_connect.config(command=lambda: self.toggle_connect("tcp"))
        
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        
        self.view.entry_zero.bind("<Return>", self.on_zero_confirm)
        self.view.btn_zero_up.command = lambda: self.adjust_zero(-0.5)
        self.view.btn_zero_down.command = lambda: self.adjust_zero(0.5)
        
        self.view.joy1.tag_bind(self.view.joy1.knob, "<B1-Motion>", self.on_drag_joy1)
        self.view.joy1.tag_bind(self.view.joy1.knob, "<ButtonRelease-1>", self.on_release_joy1)
        self.view.joy1.tag_bind(self.view.joy1.knob, "<Button-1>", lambda e: setattr(self, 'joy1_dragging', True))

        self.view.joy2.tag_bind(self.view.joy2.knob, "<B1-Motion>", self.on_drag_joy2)
        self.view.joy2.tag_bind(self.view.joy2.knob, "<ButtonRelease-1>", self.on_release_joy2)


    def send_update_packet(self, force=False):
        now = time.time()
        if force or (now - self.last_send_time > 0.05):
            m_int = int(self.val_m)
            t_int = int(self.val_t)
            cmd_str = f"#{m_int},{t_int},{self.val_zero:.2f},{self.val_h:.1f},{self.val_r:.2f}\r\n"
            self.comms.send(cmd_str)
            self.last_send_time = now

            self.view.lbl_speed.config(text=f"{self.val_m:+04d}")
            self.view.lbl_turn.config(text=f"{self.val_t:+04d}")
            self.view.lbl_r.config(text=f"{self.val_r:.1f}")
            self.view.lbl_h.config(text=f"{self.val_h:.1f}")

    # ============================================================
    #  【修改点】输入处理：增加了 I / K 键判断
    # ============================================================
    def on_key_press(self, event):
        key = event.keysym.lower()
        
        # 1. 移动
        if key in self.keys_move:
            self.keys_move[key] = True
            
        # 2. 姿态
        elif event.keysym in self.keys_pose:
            k = event.keysym
            if not self.keys_pose[k]:
                self.keys_pose[k] = True
                self.step_pose_value(k)

        # 3. 机械零点
        elif key == 'i':
            # 对应 btn_zero_up
            self.adjust_zero(-0.5)
        elif key == 'k':
            # 对应 btn_zero_down
            self.adjust_zero(0.5)

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in self.keys_move:
            self.keys_move[key] = False
            if not any(self.keys_move.values()):
                self.force_stop_sequence()
        elif event.keysym in self.keys_pose:
            self.keys_pose[event.keysym] = False

    def force_stop_sequence(self):
        print("--- [ACTION] STOP ---")
        self.val_m = 0
        self.val_t = 0
        self.send_update_packet(force=True)
        c = DIMS["joy_size"] // 2
        self.view.joy1.update_position(c, c)

    def on_drag_joy1(self, event):
        self.joy1_dragging = True
        c, r = DIMS["joy_size"] // 2, DIMS["joy_radius"]
        dx, dy = event.x - c, event.y - c
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > r: dx, dy = dx*r/dist, dy*r/dist
        self.view.joy1.update_position(c + dx, c + dy)
        self.val_m = int(-dy/r*PARAMS["max_move"])
        self.val_t = int(-dx/r*PARAMS["max_move"])

    def on_release_joy1(self, event):
        self.joy1_dragging = False
        self.force_stop_sequence()

    def step_pose_value(self, key):
        changed = False
        # --- 修改开始 ---
        # Left 是加数值 (+)，所以要用 min 去限制它的【最大值】(r_max)
        if key == 'Left': 
            self.val_r = min(PARAMS["r_max"], self.val_r + PARAMS["r_step"])
            changed = True
            
        # Right 是减数值 (-)，所以要用 max 去限制它的【最小值】(r_min)
        elif key == 'Right': 
            self.val_r = max(PARAMS["r_min"], self.val_r - PARAMS["r_step"])
            changed = True
        # --- 修改结束 ---
        elif key == 'Up': self.val_h = min(PARAMS["h_max"], self.val_h + PARAMS["h_step"]); changed = True
        elif key == 'Down': self.val_h = max(PARAMS["h_min"], self.val_h - PARAMS["h_step"]); changed = True
        
        if changed: 
            self.update_joy2_ui_position()
            self.send_update_packet(force=True)

    def on_drag_joy2(self, event):
        self.joy2_dragging = True
        c, r = DIMS["joy_size"] // 2, DIMS["joy_radius"]
        dx, dy = event.x - c, event.y - c
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > r: dx, dy = dx*r/dist, dy*r/dist
        
        self.val_r = (-dx/r) * PARAMS["r_max"]
        self.val_h = PARAMS["h_default"] - (dy/r)*(PARAMS["h_max"]-PARAMS["h_default"])
        
        self.update_joy2_ui_position()

    def on_release_joy2(self, event): 
        self.joy2_dragging = False

    def update_joy2_ui_position(self):
        r, c = DIMS["joy_radius"], DIMS["joy_size"] // 2
        dx = -(self.val_r / PARAMS["r_max"]) * r
        dy = -((self.val_h - PARAMS["h_default"]) / (PARAMS["h_max"] - PARAMS["h_default"])) * r
        self.view.joy2.update_position(c + dx, c + dy)

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

    def log_msg(self, text):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.root.after(0, lambda: self.view.log(f"[{ts}] {text}"))

    def refresh_ports(self):
        ports = self.comms.get_ports()
        self.view.port_combo['values'] = ports
        if ports: self.view.port_combo.current(0)

    def toggle_connect(self, mode):
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

    def close_app(self):
        self.comms.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    app = Controller()

