# -*- coding: utf-8 -*-
import serial
import serial.tools.list_ports
import socket
import threading
import time

class SerialService:
    def __init__(self, log_callback=None):
        self.ser = None
        self.is_connected = False
        self.log_callback = log_callback

    def get_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def connect(self, port):
        try:
            self.ser = serial.Serial(port, 115200, timeout=0.1)
            self.is_connected = True
            threading.Thread(target=self._read_loop, daemon=True).start()
            return True, "SERIAL OK"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        self.is_connected = False
        if self.ser: 
            try: self.ser.close()
            except: pass
        return "SERIAL CLOSED"

    def send(self, data_str):
        if self.is_connected and self.ser:
            try:
                self.ser.write(data_str.encode('utf-8'))
            except: self.is_connected = False

    def _read_loop(self):
        while self.is_connected:
            try:
                if self.ser and self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line and self.log_callback: self.log_callback(f"[UART] {line}")
            except: break
            time.sleep(0.01)

class TCPService:
    def __init__(self, log_callback=None):
        self.client = None
        self.is_connected = False
        self.log_callback = log_callback

    def connect(self, ip, port):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(3) 
            self.client.connect((str(ip), int(port)))
            self.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.is_connected = True
            self.client.settimeout(0.1)
            threading.Thread(target=self._read_loop, daemon=True).start()
            return True, "TCP OK"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        self.is_connected = False
        if self.client:
            try: self.client.close()
            except: pass
        return "TCP CLOSED"

    # 在 TCPService 类中
    def send(self, data_str):
        if self.is_connected and self.client:
            try:
                # 方案 A: 只要发送就视为成功，不阻塞
                self.client.send(data_str.encode('utf-8'))
                
                # 方案 B (更激进): 如果你需要确保指令被立即推出去
                # 可以在 init 里设置 self.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                # 你的代码里已经有了，这很好。
            except OSError as e:
                # 出现错误（比如 BrokenPipe）时立即标记断开，防止后续卡顿
                print(f"TCP Error: {e}")
                self.is_connected = False
                self.disconnect()

    def _read_loop(self):
        while self.is_connected:
            try:
                data = self.client.recv(1024).decode('utf-8', errors='ignore')
                if data and self.log_callback:
                    self.log_callback(f"[TCP] {data}")
            except: pass
            time.sleep(0.1)

class HybridService:
    def __init__(self, log_callback=None):
        self.serial = SerialService(log_callback)
        self.tcp = TCPService(log_callback)

    @property
    def is_connected(self):
        return self.serial.is_connected or self.tcp.is_connected

    def get_ports(self):
        p = self.serial.get_ports()
        p.append("192.168.10.110:8080")
        return p

    def connect(self, target):
        if ":" in target:
            try:
                ip, port = target.split(":")
                return self.tcp.connect(ip.strip(), port.strip())
            except: return False, "Format Error"
        else:
            return self.serial.connect(target)

    def disconnect(self):
        self.serial.disconnect()
        self.tcp.disconnect()
        return "CLOSED"

    def send(self, data_str):
        if self.serial.is_connected: self.serial.send(data_str)
        if self.tcp.is_connected: self.tcp.send(data_str)