# -*- coding: utf-8 -*-

# --- 视觉配置 ---
COLORS = {
    "bg": "#050505",
    "grid": "#003333",
    "main": "#00ffcc",
    "accent": "#FF2D2D",
    "eva_red": "#FF2D2D",
    "warning_bg": "#1A0505",
    "dim": "#0F2A2A",
    "sec_joy": "#FFD700",  # 金色
    "alert": "#FFD700",
    "text_log": "#00ff00"
}

# --- 尺寸配置 ---
DIMS = {
    "width": 1300,
    "height": 1000,
    "joy_size": 350,
    "joy_radius": 130,
    "knob_radius": 30
}

# --- 控制参数 ---
PARAMS = {
    "max_move": 100,
    # R (Roll)
    "r_min": -30.0,
    "r_max": 30.0,
    "r_step": 3.0,
    # H (Height)
    "h_default": 110.0,
    "h_min": 83.0,
    "h_max": 137.0,
    "h_step": 2.7,
    
    "send_interval": 0.15
}


# --- config.py ---
TCP_CONFIG = {
    "default_ip": "192.168.10.110",
    "default_port": 8080
}

