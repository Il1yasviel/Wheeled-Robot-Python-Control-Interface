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
        print(f"--- [DEBUG] Serial Connecting to {port} ---")
        try:
            self.ser = serial.Serial(port, 115200, timeout=0.1)
            self.is_connected = True
            threading.Thread(target=self._read_loop, daemon=True).start()
            print(f"--- [SUCCESS] UART Connected ---")
            return True, f"SERIAL OK"
        except Exception as e:
            print(f"--- [ERROR] UART Fail: {e} ---")
            return False, str(e)

    def disconnect(self):
        self.is_connected = False
        if self.ser: 
            self.ser.close()
            print("--- [DEBUG] UART Socket Closed ---")
        return "SERIAL CLOSED"

    def send(self, data_str):
        if self.is_connected and self.ser:
            self.ser.write(data_str.encode('utf-8'))

    def _read_loop(self):
        while self.is_connected:
            try:
                if self.ser.in_waiting:
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
        # 强制控制台打印
        print(f"--- [DEBUG] TCP Connecting to {ip}:{port} ... ---")
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(3) 
            self.client.connect((str(ip), int(port)))
            self.is_connected = True
            self.client.settimeout(0.1)
            threading.Thread(target=self._read_loop, daemon=True).start()
            print(f"--- [SUCCESS] TCP Connected! ---")
            return True, "TCP OK"
        except Exception as e:
            print(f"--- [ERROR] TCP Fail: {e} ---")
            self.is_connected = False
            return False, str(e)

    def disconnect(self):
        self.is_connected = False
        if self.client:
            try:
                self.client.close()
                print("--- [DEBUG] TCP Socket Closed ---")
            except: pass
        return "TCP CLOSED"

    def send(self, data_str):
        if self.is_connected and self.client:
            try:
                self.client.send(data_str.encode('utf-8'))
            except:
                self.is_connected = False

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
        print(f"--- [DEBUG] HybridService.connect called with: {target} ---")
        if ":" in target:
            try:
                ip, port = target.split(":")
                return self.tcp.connect(ip.strip(), port.strip())
            except Exception as e:
                print(f"--- [ERROR] Target split fail: {e} ---")
                return False, "Format Error"
        else:
            return self.serial.connect(target)

    def disconnect(self):
        print("--- [DEBUG] HybridService.disconnect called ---")
        self.serial.disconnect()
        self.tcp.disconnect()
        return "CLOSED"

    def send(self, data_str):
        if self.serial.is_connected: self.serial.send(data_str)
        if self.tcp.is_connected: self.tcp.send(data_str)