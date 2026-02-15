# -*- coding: utf-8 -*-
import tkinter as tk  # 导入 tkinter GUI 工具包，并将其重命名为 tk
import random  # 导入 random 模块，用于生成随机数（如随机显示的日志数据）
from config import COLORS, DIMS  # 从本地 config.py 文件中导入颜色字典和尺寸字典配置

class CyberCanvas(tk.Canvas):
    """基础画布类，包含通用绘图方法，是所有自定义组件的基类"""
    def __init__(self, parent, **kwargs):
        # 修复点：使用 setdefault 设置默认参数，确保在没有传入特定值时使用配置文件的默认色
        # 如果 kwargs 字典里已经有 'bg' 键，就不覆盖它（保护子类特定的颜色设置）
        kwargs.setdefault("bg", COLORS["bg"])  # 设置默认背景颜色
        # 默认去掉画布边框的厚度，使其与背景无缝融合，如果不设为0，Canvas周围会有白色边框
        kwargs.setdefault("highlightthickness", 0)  # 设置高亮边框厚度为 0
        
        # 调用父类 tk.Canvas 的构造函数来初始化画布
        super().__init__(parent, **kwargs)  # 将父容器和处理后的参数传递给父类

    def draw_radar_grid(self, size, center, label_text, color_theme):
        """绘制雷达网格背景，包含方格线、中心轴和同心圆"""
        step = 40  # 定义网格线的间距为 40 像素
        # 绘制背景暗色细网格，循环遍历从 0 到 size 的范围
        for i in range(0, size + 1, step):
            self.create_line(i, 0, i, size, fill="#081818")  # 绘制垂直线，颜色为深黑绿色
            self.create_line(0, i, size, i, fill="#081818")  # 绘制水平线，颜色为深黑绿色
        
        # 绘制中心十字轴线（加粗，使用配置中的网格主色）
        # 绘制垂直中心轴
        self.create_line(center, 0, center, size, fill=COLORS["grid"], width=2)
        # 绘制水平中心轴
        self.create_line(0, center, size, center, fill=COLORS["grid"], width=2)
        
        # 绘制三个同心圆，模拟雷达扫描范围，半径分别为 50, 100, 130
        for r in [50, 100, 130]:
            # 使用 create_oval 绘制圆，通过外接矩形坐标 (x1, y1, x2, y2) 定义
            self.create_oval(center - r, center - r, center + r, center + r, outline=COLORS["dim"], width=1)
        
        # 在底部绘制摇杆的名称标签（如 LOCOMOTION）
        # 坐标为 (center, size - 20)，文字颜色灰色，字体 Impact 10号
        self.create_text(center, size - 20, text=label_text, fill="gray", font=("Impact", 10))

class JoystickWidget(CyberCanvas):
    """摇杆组件：实时显示摇杆帽的位置"""
    def __init__(self, parent, size, label, color_theme):
        # 初始化画布，并设置高亮边框颜色
        # 调用父类构造函数，设置宽高、黑色背景、2像素的高亮边框
        super().__init__(parent, width=size, height=size, bg="#000000", 
                         highlightthickness=2, highlightbackground=COLORS["grid"])
        self.size = size                   # 保存画布尺寸
        self.center = size // 2            # 计算并保存中心点坐标（整数除法）
        self.radius = DIMS["knob_radius"]  # 从配置中获取摇杆帽的半径
        self.color = color_theme           # 保存摇杆的主题颜色（如红色或金色）
        
        # 绘制底层雷达网格背景
        self.draw_radar_grid(size, self.center, label, color_theme)
        
        # 初始化旋钮图形：glow (发光层)、knob (主体层)、center (中心小白点)
        # stipple="gray50" 用于实现半透明点阵效果，模拟发光
        self.knob_glow = self.create_oval(0, 0, 0, 0, fill=color_theme, outline="", stipple="gray50")
        # 绘制摇杆主体圆，填充黑色，边框为主题色，线宽 3
        self.knob = self.create_oval(0, 0, 0, 0, fill="black", outline=color_theme, width=3)
        # 绘制中心装饰点，填充白色
        self.knob_center = self.create_oval(0, 0, 0, 0, fill="white", outline="")
        
        # 将摇杆初始位置设在画布中心
        self.update_position(self.center, self.center)

    def update_position(self, x, y):
        """更新摇杆图形在画布上的坐标"""
        r = self.radius  # 获取半径便捷变量
        # 更新主体圆圈位置，coords 方法接收 (ID, x1, y1, x2, y2)
        self.coords(self.knob, x - r, y - r, x + r, y + r)
        # 更新外围发光扩散层（比主体大 8 像素）
        gr = r + 8  # 计算发光层半径
        self.coords(self.knob_glow, x - gr, y - gr, x + gr, y + gr)
        # 更新中心装饰点位置（固定半径为 3）
        self.coords(self.knob_center, x - 3, y - 3, x + 3, y + 3)

class DecorPanel(CyberCanvas):
    """左右两侧的装饰面板：显示虚假的系统数据和状态，增强氛围感"""
    def __init__(self, parent, side,width,height):
        # 宽度固定为 160 像素，高度由传入参数决定
        super().__init__(parent, width=width, height=height)
        self.w = width # 存一下宽度
        self.draw_decor(side, height)  # 调用绘制装饰内容的方法

    def draw_decor(self, side, h):
        w = self.w # 使用传入的动态宽度
        # 绘制背景水平装饰线，每隔 20 像素画一条
        for i in range(0, h, 20):
            self.create_line(0, i, w, i, fill="#050a0a")  # 极暗的线条作为背景纹理

        if side == "left":  # 如果是左侧面板
            # 进度条靠右侧边缘放置 (w - 20)
            self.create_rectangle(w-20, 50, w-10, h-50, outline=COLORS["grid"], width=2)
            # 绘制进度条内部的小色块，从 60 到 h-60，步长 10
            for i in range(60, h - 60, 10):
                # 决定颜色：如果位置在下半部分 (> h/2) 则为主色，否则为警告红（模拟EVA风格）
                color = COLORS["main"] if i > h / 2 else COLORS["eva_red"] # 下半部分变红
                if i % 30 == 0: # 模运算，每隔 3 个位置 (30像素) 绘制一个矩形，形成间断效果
                    self.create_rectangle(142, i, 148, i + 6, fill=color, outline="")
            
            # 绘制伪造的系统内核 16 进制转储日志
            # 2. 核心修复：文字坐标必须保证其开头不会跌破 x=0
            # 建议将 x_text 设为相对于 w 的值。
            # 比如 w=270, x_text=w-30 (即 240)。
            # 只要 w-30 大于文字的总宽度，它就不会被左边界切掉。
            x_text = w - 30 
            y_text = 100  # 文字起始 y 坐标
            # 绘制标题 "SYS.KERNEL.DUMP"，右对齐
            self.create_text(x_text, 60, text="SYS.KERNEL.DUMP", fill="gray", font=("Consolas", 8), anchor="e")
            for _ in range(12):  # 循环生成 12 行随机数据
                # 随机生成 3 组 HEX 字符 (0-255)，格式化为2位十六进制大写，用空格连接
                hex_str = ' '.join([f"{random.randint(0, 255):02X}" for _ in range(3)])
                # 绘制一行文本，字体 Consolas 9号，颜色暗淡
                self.create_text(x_text, y_text, text=hex_str, fill=COLORS["dim"], font=("Consolas", 9), anchor="e")
                y_text += 20  # y 坐标增加，换行
            
            # 绘制左下角“高压危险”警告标志
            # 绘制外框
            self.create_rectangle(10, h - 150, 100, h - 50, outline=COLORS["accent"], width=2)
            # 绘制警告文字，居中对齐
            self.create_text(55, h - 100, text="CAUTION\nHIGH VOLT", fill=COLORS["accent"], font=("Impact", 10), justify="center")

        elif side == "right":  # 如果是右侧面板
            # 绘制右侧系统状态列表（陀螺仪、温度、燃料等）
            x_base = 0   # 基础 x 坐标
            y_base = 0   # 基础 y 坐标

            # 定义状态文本列表
            statuses = ["yi: er", "san: si", "wu: liu", "qi: ba", "jiu: shi", "ready? OK"]
            for s in statuses:  # 遍历状态列表
                self.create_rectangle(x_base, y_base, x_base + 5, y_base + 5, fill=COLORS["main"]) # 绘制每行前面的小方块修饰
                # 绘制状态文本，左对齐
                self.create_text(x_base + 15, y_base + 3, text=s, fill=COLORS["main"], font=("Consolas", 10), anchor="w")
                y_base += 22  # y 坐标增加，换行



            # === 平移参数设定 ===
            shift_x = 100  # 向右平移 20 像素
            shift_y = -100  # 向上平移 30 像素
            # 绘制中间的感叹号警告图标（三角形多边形）
            icon_y = 120+shift_y  # 图标的基础 y 坐标
            p1 = (95+shift_x, icon_y)        # 三角形顶点
            p2 = (65+shift_x, icon_y + 50)   # 三角形左下点
            p3 = (125+shift_x, icon_y + 50)  # 三角形右下点
            # 绘制空心三角形
            self.create_polygon(p1, p2, p3, outline=COLORS["alert"], fill="", width=3)
            # 在三角形中间绘制感叹号
            self.create_text(95+shift_x, icon_y + 30, text="!", fill=COLORS["alert"], font=("Impact", 24))
            # 在三角形下方绘制 "PREPARING..." 文字
            self.create_text(95+shift_x, icon_y + 70, text="PREPARING...", fill=COLORS["eva_red"], font=("Impact", 12))
            
            # 绘制右下角红色“无信号”警告框
            # 绘制填充为背景色、边框为红色的矩形
            self.create_rectangle(50, h - 110, 140, h - 10, fill=COLORS["warning_bg"], outline=COLORS["eva_red"])
            # 绘制 "NO SIGNAL" 文字
            self.create_text(95, h - 60, text="NO\nSIGNAL", fill=COLORS["eva_red"], font=("Impact", 14), justify="center")

class WarningStrip(CyberCanvas):
    """警告装饰带：用于显示巨大的“MANUAL OVERRIDE”文字和斜纹条"""
    def __init__(self, parent, width, height):
        # 初始化父类
        super().__init__(parent, height=height)
        self.draw_stripes(height) # 调用方法绘制背景斜纹
        # 绘制中央巨型警告文字，位置居中 (650, height/2)
        self.create_text(width / 2, height / 2, text="M A N U A L   O V E R R I D E", 
                         font=("Impact", 32), fill=COLORS["eva_red"])

    def draw_stripes(self, height):
        """在区域顶部和底部绘制斜向警戒纹"""
        # 绘制背景底色矩形，宽度设为 2000 以确保覆盖全屏
        self.create_rectangle(0, 0, 2000, height, fill=COLORS["warning_bg"], width=0)
        stripe_h = 15  # 定义条纹的高度
        self._draw_row(0, stripe_h) # 在顶部 y=0 处绘制一行条纹
        self._draw_row(height - stripe_h, stripe_h) # 在底部绘制一行条纹

    def _draw_row(self, y_pos, h):
        """内部方法：循环绘制平行四边形组成斜纹"""
        stripe_width = 30  # 单个条纹的宽度
        gap = 50           # 条纹之间的间隔
        # 循环 x 坐标，从 -50 到 2000，步长为 gap
        for x in range(-50, 2000, gap):
            # 定义平行四边形四个顶点的坐标 (x1,y1, x2,y2, x3,y3, x4,y4)，形成倾斜效果
            points = [x, y_pos + h, x + stripe_width, y_pos + h, x + stripe_width + 20, y_pos, x + 20, y_pos]
            # 绘制多边形，填充红色
            self.create_polygon(points, fill=COLORS["eva_red"])


class EvaButton(tk.Canvas):
    """
    自定义的 EVA 风格按钮：
    不使用系统按钮组件，完全用画布绘制以控制像素级的反色效果
    """
    def __init__(self, parent, width, height, text, command=None, font_size=10):
        # 初始化小型画布作为按钮基础，背景黑，无边框
        super().__init__(parent, width=width, height=height, bg="black", highlightthickness=0)
        self.command = command         # 存储点击时的回调函数
        self.text_str = text           # 存储按钮显示的文字
        self.width = width             # 存储宽度
        self.height = height           # 存储高度
        self.font_size = font_size     # 存储字号
        
        # 定义颜色方案：默认状态黑底红字，激活状态红底黑字（EVA终端风格）
        self.col_bg_norm = "black"             # 正常背景色
        self.col_fg_norm = COLORS["eva_red"]   # 正常前景色
        self.col_bg_act = COLORS["eva_red"]    # 激活背景色
        self.col_fg_act = "black"              # 激活前景色
        
        # 绘制初始（正常）状态的按钮图形
        self.draw_normal()
        
        # 绑定鼠标左键按下事件，触发 on_press
        self.bind("<Button-1>", self.on_press)
        # 绑定鼠标左键释放事件，触发 on_release
        self.bind("<ButtonRelease-1>", self.on_release)

    def draw_normal(self):
        """绘制正常状态：黑底红字红框"""
        self.delete("all") # 清空画布上的所有旧图形
        # 绘制外边框和背景矩形
        self.create_rectangle(0, 0, self.width-1, self.height-1, 
                              outline=self.col_fg_norm, fill=self.col_bg_norm, width=2)
        # 绘制按钮文字，居中
        self.create_text(self.width/2, self.height/2, text=self.text_str, 
                         fill=self.col_fg_norm, font=("Arial", self.font_size, "bold"))

    def draw_active(self):
        """绘制点击状态：反色处理"""
        self.delete("all") # 清空画布
        # 填充背景为红色（激活色），边框保持原色
        self.create_rectangle(0, 0, self.width-1, self.height-1, 
                              outline=self.col_fg_norm, fill=self.col_bg_act, width=2)
        # 文字变为黑色（激活前景色）
        self.create_text(self.width/2, self.height/2, text=self.text_str, 
                         fill=self.col_fg_act, font=("Arial", self.font_size, "bold"))

    def on_press(self, event):
        """按下鼠标时切换为激活状态图形"""
        self.draw_active() # 重绘为激活样式

    def on_release(self, event):
        """抬起鼠标时恢复正常状态，并执行回调指令"""
        self.draw_normal() # 重绘为正常样式
        if self.command:   # 如果初始化时传入了 command 函数
            self.command() # 执行该函数