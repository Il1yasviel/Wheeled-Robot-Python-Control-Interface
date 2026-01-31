# -*- coding: utf-8 -*-
import tkinter as tk
import random
from config import COLORS, DIMS

class CyberCanvas(tk.Canvas):
    """基础画布类，包含通用绘图方法"""
    def __init__(self, parent, **kwargs):
        # 修复点：使用 setdefault 设置默认值
        # 如果 kwargs 里已经有 'bg' (比如 JoystickWidget 传进来的)，就不覆盖
        # 如果没有，就使用 config 里的默认背景色
        kwargs.setdefault("bg", COLORS["bg"])
        kwargs.setdefault("highlightthickness", 0)
        
        super().__init__(parent, **kwargs)

    def draw_radar_grid(self, size, center, label_text, color_theme):
        # ... (这部分代码保持不变) ...
        step = 40
        for i in range(0, size + 1, step):
            self.create_line(i, 0, i, size, fill="#081818")
            self.create_line(0, i, size, i, fill="#081818")
        self.create_line(center, 0, center, size, fill=COLORS["grid"], width=2)
        self.create_line(0, center, size, center, fill=COLORS["grid"], width=2)
        for r in [50, 100, 130]:
            self.create_oval(center - r, center - r, center + r, center + r, outline=COLORS["dim"], width=1)
        self.create_text(center, size - 20, text=label_text, fill="gray", font=("Impact", 10))

class JoystickWidget(CyberCanvas):
    """摇杆组件"""
    def __init__(self, parent, size, label, color_theme):
        super().__init__(parent, width=size, height=size, bg="#000000", 
                         highlightthickness=2, highlightbackground=COLORS["grid"])
        self.size = size
        self.center = size // 2
        self.radius = DIMS["knob_radius"]
        self.color = color_theme
        
        self.draw_radar_grid(size, self.center, label, color_theme)
        
        # 初始化旋钮图形
        self.knob_glow = self.create_oval(0, 0, 0, 0, fill=color_theme, outline="", stipple="gray50")
        self.knob = self.create_oval(0, 0, 0, 0, fill="black", outline=color_theme, width=3)
        self.knob_center = self.create_oval(0, 0, 0, 0, fill="white", outline="")
        
        self.update_position(self.center, self.center)

    def update_position(self, x, y):
        r = self.radius
        self.coords(self.knob, x - r, y - r, x + r, y + r)
        gr = r + 8
        self.coords(self.knob_glow, x - gr, y - gr, x + gr, y + gr)
        self.coords(self.knob_center, x - 3, y - 3, x + 3, y + 3)

class DecorPanel(CyberCanvas):
    """左右两侧的装饰面板"""
    def __init__(self, parent, side, height):
        super().__init__(parent, width=160, height=height)
        self.draw_decor(side, height)

    def draw_decor(self, side, h):
        w = 160
        # 背景线
        for i in range(0, h, 20):
            self.create_line(0, i, w, i, fill="#050a0a")

        if side == "left":
            self.create_rectangle(140, 50, 150, h - 50, outline=COLORS["grid"], width=2)
            for i in range(60, h - 60, 10):
                color = COLORS["main"] if i > h / 2 else COLORS["eva_red"]
                if i % 30 == 0:
                    self.create_rectangle(142, i, 148, i + 6, fill=color, outline="")
            
            x_text = 120
            y_text = 100
            self.create_text(x_text, 60, text="SYS.KERNEL.DUMP", fill="gray", font=("Consolas", 8), anchor="e")
            for _ in range(12):
                hex_str = ' '.join([f"{random.randint(0, 255):02X}" for _ in range(3)])
                self.create_text(x_text, y_text, text=hex_str, fill=COLORS["dim"], font=("Consolas", 9), anchor="e")
                y_text += 20
            
            self.create_rectangle(10, h - 150, 90, h - 50, outline=COLORS["accent"], width=2)
            self.create_text(50, h - 100, text="CAUTION\nHIGH VOLT", fill=COLORS["accent"], font=("Impact", 10), justify="center")

        elif side == "right":
            x_base = 60
            y_base = 20
            statuses = ["GYRO: STABLE", "TEMP: 450K", "FUEL: 98%", "AMMO: NULL", "LINK: OK", "PING: 12ms"]
            for s in statuses:
                self.create_rectangle(x_base, y_base, x_base + 5, y_base + 5, fill=COLORS["main"])
                self.create_text(x_base + 15, y_base + 3, text=s, fill=COLORS["main"], font=("Consolas", 10), anchor="w")
                y_base += 22
            
            icon_y = 120
            p1 = (95, icon_y)
            p2 = (65, icon_y + 50)
            p3 = (125, icon_y + 50)
            self.create_polygon(p1, p2, p3, outline=COLORS["alert"], fill="", width=3)
            self.create_text(95, icon_y + 30, text="!", fill=COLORS["alert"], font=("Impact", 24))
            self.create_text(95, icon_y + 70, text="PREPARING...", fill=COLORS["eva_red"], font=("Impact", 12))
            
            self.create_rectangle(50, h - 110, 140, h - 10, fill=COLORS["warning_bg"], outline=COLORS["eva_red"])
            self.create_text(95, h - 60, text="NO\nSIGNAL", fill=COLORS["eva_red"], font=("Impact", 14), justify="center")

class WarningStrip(CyberCanvas):
    """顶部和底部的警告条纹"""
    def __init__(self, parent, width, height):
        super().__init__(parent, height=height)
        self.draw_stripes(height)
        self.create_text(650, height / 2, text="M A N U A L   O V E R R I D E", 
                         font=("Impact", 32), fill=COLORS["eva_red"])

    def draw_stripes(self, height):
        self.create_rectangle(0, 0, 2000, height, fill=COLORS["warning_bg"], width=0)
        stripe_h = 15
        self._draw_row(0, stripe_h)
        self._draw_row(height - stripe_h, stripe_h)

    def _draw_row(self, y_pos, h):
        stripe_width = 30
        gap = 50
        for x in range(-50, 2000, gap):
            points = [x, y_pos + h, x + stripe_width, y_pos + h, x + stripe_width + 20, y_pos, x + 20, y_pos]
            self.create_polygon(points, fill=COLORS["eva_red"])


class EvaButton(tk.Canvas):
    """
    自定义的 EVA 风格按钮 (Canvas 绘制)
    绕过 ttkbootstrap 的蓝色主题，实现黑底红字/红底黑字的像素风格
    """
    def __init__(self, parent, width, height, text, command=None, font_size=10):
        super().__init__(parent, width=width, height=height, bg="black", highlightthickness=0)
        self.command = command
        self.text_str = text
        self.width = width
        self.height = height
        self.font_size = font_size
        
        # 颜色定义
        self.col_bg_norm = "black"
        self.col_fg_norm = COLORS["eva_red"]
        self.col_bg_act = COLORS["eva_red"]
        self.col_fg_act = "black"
        
        # 绘制初始状态
        self.draw_normal()
        
        # 绑定事件
        self.bind("<Button-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)

    def draw_normal(self):
        self.delete("all")
        # 边框
        self.create_rectangle(0, 0, self.width-1, self.height-1, 
                              outline=self.col_fg_norm, fill=self.col_bg_norm, width=2)
        # 文字/箭头
        self.create_text(self.width/2, self.height/2, text=self.text_str, 
                         fill=self.col_fg_norm, font=("Arial", self.font_size, "bold"))

    def draw_active(self):
        self.delete("all")
        # 填充背景为红色
        self.create_rectangle(0, 0, self.width-1, self.height-1, 
                              outline=self.col_fg_norm, fill=self.col_bg_act, width=2)
        # 文字变黑
        self.create_text(self.width/2, self.height/2, text=self.text_str, 
                         fill=self.col_fg_act, font=("Arial", self.font_size, "bold"))

    def on_press(self, event):
        self.draw_active()

    def on_release(self, event):
        self.draw_normal()
        if self.command:
            self.command()
