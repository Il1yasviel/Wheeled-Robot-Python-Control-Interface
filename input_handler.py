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
        # --- 新增：将写死的配置转为动态变量 ---
        self.max_x_offset = PARAMS.get("max_x_offset", 100) 

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

        # 5. 【新增】摇杆 4 (Y/H 纵向轴)
        joy_yh = self.app.view.joy_yh
        joy_yh.tag_bind(joy_yh.knob, "<B1-Motion>", self.on_yh_drag)
        joy_yh.tag_bind(joy_yh.knob, "<ButtonRelease-1>", self.on_yh_release)


    # ============================================================
    # 键盘控制逻辑
    # ============================================================
    def calc_speed_from_keys(self):
        tx, ty = 0, 0
        r = DIMS["joy_radius"]
        
        if self.app.keys_move['w']: ty -= r * 1.0
        if self.app.keys_move['s']: ty += r * 1.0
        if self.app.keys_move['a']: tx -= r * 0.9
        if self.app.keys_move['d']: tx += r * 0.9
        
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
            self.app.adjust_zero(-0.1)
        elif key == 'k':
            self.app.adjust_zero(0.1)

        if key == 'y':
            self.app.val_yh = -self.max_x_offset
            self.update_yh_ui_position()
            self.app.send_update_packet(force=True) # <--- 立刻发包
        elif key == 'h':
            self.app.val_yh = self.max_x_offset
            self.update_yh_ui_position()
            self.app.send_update_packet(force=True) # <--- 立刻发包

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in self.app.keys_move:
            self.app.keys_move[key] = False
            if not any(self.app.keys_move.values()):
                self.force_stop_sequence()
        elif event.keysym in self.app.keys_pose:
            self.app.keys_pose[event.keysym] = False
        # 松开 Y/H 键时，不但数值归零，还要立刻发送一次指令
        if key in ['y', 'h']:
            self.app.val_yh = 0
            self.update_yh_ui_position()
            self.app.send_update_packet(force=True) # <--- 立刻告诉单片机：回到中心！

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



    # === 【新增逻辑】纵向摇杆鼠标控制 ===
    def on_yh_drag(self, event):
        joy = self.app.view.joy_yh
        center = joy.size // 2
        radius = joy.radius
        
        # 核心修改：忽略 event.x，强行让 dx = 0，实现“只能前后”
        dx = 0 
        dy = event.y - center
        
        # 距离限幅
        if abs(dy) > radius:
            dy = radius if dy > 0 else -radius
            
        # UI 更新：仅在垂直方向移动
        joy.update_position(center, center + dy)
        
        # 计算数值映射到 PARAMS["max_move"]
        # 向上为正(Y)，向下为负(H)
        # 修改这里：使用动态的 self.max_x_offset
        self.app.val_yh = int(-(dy / radius) * self.max_x_offset)  
        self.app.send_update_packet(force=True) 

    def on_yh_release(self, event):
        self.app.val_yh = 0
        c = self.app.view.joy_yh.size // 2
        self.app.view.joy_yh.update_position(c, c)
        # 松开鼠标摇杆时，立刻强制发包
        self.app.send_update_packet(force=True) # <--- 立刻告诉单片机：回到中心！
       

    # 辅助方法：根据数值更新摇杆球位置
    def update_yh_ui_position(self):
        joy = self.app.view.joy_yh
        c = joy.size // 2
        r = joy.radius
        # 反向映射：val_yh -> dy
        # 修改这里：防止除以 0 的保险逻辑，并使用 self.max_x_offset
        limit = self.max_x_offset if self.max_x_offset != 0 else 1
        dy = -(self.app.val_yh / limit) * r
        joy.update_position(c, c + dy)   