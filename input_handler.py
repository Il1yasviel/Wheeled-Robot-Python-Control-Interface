# -*- coding: utf-8 -*-
import math
from config import DIMS, PARAMS

# 1. 导入专门用于类型检查的模块
from typing import TYPE_CHECKING

# 2. 这个代码块只在“编辑器进行代码检查”时运行，真实运行时会被直接跳过
if TYPE_CHECKING:
    # 注意：这里的 'main' 是你主程序文件的名字（如果不叫 main.py 请改成对应的名字）
    from main import Controller 

class InputHandler:
    def __init__(self, app: 'Controller'):       #主要是用于代码补全，能快速跳转函数
        # 这里的 app 就是 Controller 的实例 (self)
        self.app = app

    def bind_all(self):
        """集中绑定所有的键盘和鼠标事件"""
        # 1. 键盘全局事件
        self.app.root.bind("<KeyPress>", self.on_key_press)
        self.app.root.bind("<KeyRelease>", self.on_key_release)
        
        # 2. 摇杆 1 (移动)
        joy1 = self.app.view.joy1
        joy1.tag_bind(joy1.knob, "<B1-Motion>", self.on_drag_joy1)
        joy1.tag_bind(joy1.knob, "<ButtonRelease-1>", self.on_release_joy1)
        joy1.tag_bind(joy1.knob, "<Button-1>", lambda e: setattr(self.app, 'joy1_dragging', True))

        # 3. 摇杆 2 (姿态)
        joy2 = self.app.view.joy2
        joy2.tag_bind(joy2.knob, "<B1-Motion>", self.on_drag_joy2)
        joy2.tag_bind(joy2.knob, "<ButtonRelease-1>", self.on_release_joy2)

        # 4. 摇杆 3 (云台)
        joy_gimbal = self.app.view.joy_gimbal
        joy_gimbal.tag_bind(joy_gimbal.knob, "<B1-Motion>", self.on_gimbal_drag)
        joy_gimbal.tag_bind(joy_gimbal.knob, "<ButtonRelease-1>", self.on_gimbal_release)
        joy_gimbal.tag_bind(joy_gimbal.knob, "<Button-1>", lambda e: setattr(self.app, 'gimbal_active', True))

    # ============================================================
    # ★ 键盘控制逻辑
    # ============================================================
    def calc_speed_from_keys(self):
        tx, ty = 0, 0
        r = DIMS["joy_radius"]
        
        if self.app.keys_move['w']: ty -= r * 0.2 
        if self.app.keys_move['s']: ty += r * 0.2
        if self.app.keys_move['a']: tx -= r * 1.0
        if self.app.keys_move['d']: tx += r * 1.0
        
        dist = math.sqrt(tx*tx + ty*ty)
        if dist > r:
            tx = tx * r / dist
            ty = ty * r / dist

        c = DIMS["joy_size"] // 2
        self.app.view.joy1.update_position(c + tx, c + ty)

        self.app.val_m = int(-ty / r * PARAMS["max_move"])
        self.app.val_t = int(-tx / r * PARAMS["max_move"])

    def step_pose_value(self, key):
        changed = False
        if key == 'Left': 
            self.app.val_r = min(PARAMS["r_max"], self.app.val_r + PARAMS["r_step"])
            changed = True
        elif key == 'Right': 
            self.app.val_r = max(PARAMS["r_min"], self.app.val_r - PARAMS["r_step"])
            changed = True
        elif key == 'Up': 
            self.app.val_h = min(PARAMS["h_max"], self.app.val_h + PARAMS["h_step"])
            changed = True
        elif key == 'Down': 
            self.app.val_h = max(PARAMS["h_min"], self.app.val_h - PARAMS["h_step"])
            changed = True
        
        if changed: 
            self.update_joy2_ui_position()
            self.app.send_update_packet(force=True)

    def force_stop_sequence(self):
        print("--- [ACTION] STOP ---")
        self.app.val_m = 0
        self.app.val_t = 0
        self.app.send_update_packet(force=True)
        c = DIMS["joy_size"] // 2
        self.app.view.joy1.update_position(c, c)

    def on_key_press(self, event):
        key = event.keysym.lower()
        if key in self.app.keys_move:
            self.app.keys_move[key] = True
        elif event.keysym in self.app.keys_pose:
            k = event.keysym
            if not self.app.keys_pose[k]:
                self.app.keys_pose[k] = True
                self.step_pose_value(k)
        elif key == 'i':
            self.app.adjust_zero(-0.5)
        elif key == 'k':
            self.app.adjust_zero(0.5)

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in self.app.keys_move:
            self.app.keys_move[key] = False
            if not any(self.app.keys_move.values()):
                self.force_stop_sequence()
        elif event.keysym in self.app.keys_pose:
            self.app.keys_pose[event.keysym] = False

    # ============================================================
    # ★ 鼠标摇杆控制逻辑
    # ============================================================
    def on_drag_joy1(self, event):
        self.app.joy1_dragging = True
        c, r = DIMS["joy_size"] // 2, DIMS["joy_radius"]
        dx, dy = event.x - c, event.y - c
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > r: dx, dy = dx*r/dist, dy*r/dist
        self.app.view.joy1.update_position(c + dx, c + dy)
        self.app.val_m = int(-dy/r*PARAMS["max_move"])
        self.app.val_t = int(-dx/r*PARAMS["max_move"])

    def on_release_joy1(self, event):
        self.app.joy1_dragging = False
        self.force_stop_sequence()

    def on_drag_joy2(self, event):
        self.app.joy2_dragging = True
        c, r = DIMS["joy_size"] // 2, DIMS["joy_radius"]
        dx, dy = event.x - c, event.y - c
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > r: dx, dy = dx*r/dist, dy*r/dist
        
        self.app.val_r = (-dx/r) * PARAMS["r_max"]
        self.app.val_h = PARAMS["h_default"] - (dy/r)*(PARAMS["h_max"]-PARAMS["h_default"])
        self.update_joy2_ui_position()

    def on_release_joy2(self, event): 
        self.app.joy2_dragging = False

    def update_joy2_ui_position(self):
        r, c = DIMS["joy_radius"], DIMS["joy_size"] // 2
        dx = -(self.app.val_r / PARAMS["r_max"]) * r
        dy = -((self.app.val_h - PARAMS["h_default"]) / (PARAMS["h_max"] - PARAMS["h_default"])) * r
        self.app.view.joy2.update_position(c + dx, c + dy)

    # ============================================================
    # ★ 云台控制逻辑
    # ============================================================
    def on_gimbal_drag(self, event):
        if not self.app.gimbal_override_enabled:
            return 

        self.app.gimbal_active = True
        joy = self.app.view.joy_gimbal
        center = joy.size // 2
        radius = joy.radius
        
        dx = event.x - center
        dy = event.y - center
        distance = (dx**2 + dy**2) ** 0.5
        
        if distance > radius:
            scale = radius / distance
            dx *= scale
            dy *= scale
            
        joy.update_position(center + dx, center + dy)
        
        pan_angle = int(90 - (dx / radius) * 90)
        tilt_angle = int(90 + (dy / radius) * 90)
        
        self.app.current_pan = max(0, min(180, pan_angle))
        self.app.current_tilt = max(0, min(150, tilt_angle))
        
        self.app.send_gimbal_udp(self.app.current_pan, self.app.current_tilt)

    def on_gimbal_release(self, event):
        if not self.app.gimbal_override_enabled:
            return 

        self.app.gimbal_active = False
        c = self.app.view.joy_gimbal.size // 2
        self.app.view.joy_gimbal.update_position(c, c)
        
        self.app.current_pan = 90.0
        self.app.current_tilt = 90.0
        self.app.send_gimbal_udp(90, 90)