# -*- coding: utf-8 -*-
# 导入串口通信库，用于和物理串口（如 USB 转串口）交互
import serial
# 导入串口工具库，用于列出电脑上当前可用的所有串口设备
import serial.tools.list_ports
# 导入网络套接字库，用于 TCP/IP 协议的网络通信
import socket
# 导入多线程库，用于在后台持续读取数据，防止主界面卡死
import threading
# 导入时间库，用于控制循环中的延时
import time

# 定义串口服务类
class SerialService:
    def __init__(self, log_callback=None):
        # 初始化串口对象为 None
        self.ser = None
        # 初始化连接状态标志位为 False
        self.is_connected = False
        # 设置日志回调函数，用于将收到的数据传递给外部显示（如 UI 界面）
        self.log_callback = log_callback

    def get_ports(self):
        # 获取并返回当前系统中所有可用的串口名称列表（如 ['COM1', 'COM2']）
        return [port.device for port in serial.tools.list_ports.comports()]

    def connect(self, port):
        try:
            # 尝试打开指定串口，波特率 115200，读取超时时间 0.1 秒
            self.ser = serial.Serial(port, 115200, timeout=0.1)
            # 如果没报错，标记连接成功
            self.is_connected = True
            # 开启一个守护线程（daemon=True），该线程会在后台运行读取循环
            threading.Thread(target=self._read_loop, daemon=True).start()
            # 返回成功状态和提示信息
            return True, "SERIAL OK"
        except Exception as e:
            # 如果发生错误（如串口被占用），返回失败状态和错误信息
            return False, str(e)

    def disconnect(self):
        # 将连接状态标记为断开，这会使读取循环停止
        self.is_connected = False
        # 如果串口对象存在
        if self.ser: 
            try: 
                # 尝试关闭串口硬件连接
                self.ser.close()
            except: 
                # 忽略关闭时的异常
                pass
        # 返回已关闭的提示
        return "SERIAL CLOSED"

    def send(self, data_str):
        # 只有在已连接且对象有效的情况下才发送
        if self.is_connected and self.ser:
            try:
                # 将字符串编码为 utf-8 字节流并写入串口
                self.ser.write(data_str.encode('utf-8'))
            except: 
                # 如果发送出错，标记连接断开
                self.is_connected = False

    def _read_loop(self):
        # 这是一个后台循环，只要连接没断开就一直运行
        while self.is_connected:
            try:
                # 如果串口有效且缓冲区内有待读取的数据
                if self.ser and self.ser.in_waiting:
                    # 读取一行数据，按 utf-8 解码，忽略非法字符，并去掉首尾空格
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    # 如果读到了内容且有回调函数，则通过回调输出日志
                    if line and self.log_callback: self.log_callback(f"[UART] {line}")
            except: 
                # 发生读取异常时强制跳出循环
                break
            # 每次循环休眠 10 毫秒，避免过度占用 CPU
            time.sleep(0.01)

# 定义 TCP 网络服务类
"""class TCPService:
    def __init__(self, log_callback=None):
        # 初始化客户端套接字为 None
        self.client = None
        # 初始化连接状态标志位
        self.is_connected = False
        # 设置日志回调函数
        self.log_callback = log_callback

    def connect(self, ip, port):
        try:
            # 创建一个基于 IPv4 和 TCP 协议的套接字对象
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 设置连接过程的超时时间为 3 秒
            self.client.settimeout(3) 
            # 尝试连接目标 IP 地址和端口号
            self.client.connect((str(ip), int(port)))
            # 禁用 Nagle 算法（TCP_NODELAY），确保小数据包能立即发出，不合并延迟
            self.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # 标记连接成功
            self.is_connected = True
            # 连接建立后，将读取数据的超时时间设为 0.1 秒
            self.client.settimeout(0.1)
            # 启动后台线程执行读取循环
            threading.Thread(target=self._read_loop, daemon=True).start()
            # 返回成功状态
            return True, "TCP OK"
        except Exception as e:
            # 捕获连接异常并返回
            return False, str(e)

    def disconnect(self):
        # 标记连接断开
        self.is_connected = False
        # 如果套接字对象存在
        if self.client:
            try: 
                # 尝试关闭网络连接
                self.client.close()
            except: 
                pass
        # 返回状态提示
        return "TCP CLOSED"

    def send(self, data_str):
        # 确保在连接状态下发送
        if self.is_connected and self.client:
            try:
                # 将字符串编码后通过 TCP 发送
                self.client.send(data_str.encode('utf-8'))
            except OSError as e:
                # 如果发生系统层级的网络错误（如断网）
                print(f"TCP Error: {e}")
                # 立即标记为断开状态
                self.is_connected = False
                # 执行清理关闭操作
                self.disconnect()

    def _read_loop(self):
        # 持续读取循环
        while self.is_connected:
            try:
                # 尝试接收最大 1024 字节的数据并解码
                data = self.client.recv(1024).decode('utf-8', errors='ignore')
                # 如果接收到有效数据且存在回调
                if data and self.log_callback:
                    # 通过回调输出 TCP 日志
                    self.log_callback(f"[TCP] {data}")
            except: 
                # 超时或报错时不做处理，继续下一次循环
                pass
            # 每次读取后休眠 100 毫秒，降低资源消耗
            time.sleep(0.1)
"""

# 将原先的 TCPService 替换为 UDPService
class UDPService:
    def __init__(self, log_callback=None):
        self.client = None
        self.is_connected = False
        self.log_callback = log_callback

    def connect(self, ip, port):
        try:
            # 【核心修改 1】使用 SOCK_DGRAM 表示这是一个 UDP 套接字
            self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # 【核心修改 2】删除了 TCP_NODELAY（Nagle算法），因为 UDP 不需要这个
            
            # 【核心重点】既然 UDP 是无连接的，为什么还要调用 connect？
            # 在 Python 里，对 UDP socket 调用 connect 并不会真的去网络上握手！
            # 它只是在本地操作系统里“记住”了这个目标 IP 和端口。
            # 这样一来，我们后面就可以继续沿用 TCP 的 send() 和 recv() 方法，
            # 而不需要改用麻烦的 sendto() 和 recvfrom()。
            self.client.connect((str(ip), int(port)))
            
            self.is_connected = True
            # 设置接收数据的超时时间为 0.1 秒
            self.client.settimeout(0.1)
            
            # 启动后台读取线程
            threading.Thread(target=self._read_loop, daemon=True).start()
            return True, "UDP OK"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        self.is_connected = False
        if self.client:
            try: 
                self.client.close()
            except: 
                pass
        return "UDP CLOSED"

    def send(self, data_str):
        if self.is_connected and self.client:
            try:
                # 发送字符串（因为上面 connect 锁定了地址，这里可以直接用 send）
                self.client.send(data_str.encode('utf-8'))
            except OSError as e:
                print(f"UDP Error: {e}")
                self.is_connected = False
                self.disconnect()

    def _read_loop(self):
        while self.is_connected:
            try:
                # 接收小车回传的数据
                data = self.client.recv(1024).decode('utf-8', errors='ignore')
                if data and self.log_callback:
                    self.log_callback(f"[UDP] {data}")
            except socket.timeout:
                # UDP 超时很正常，直接忽略即可
                pass
            except Exception as e: 
                pass
            time.sleep(0.01)





#使用UDP服务，只发送不接收
class GimbalUDPService:
    def __init__(self, ip, port):
        self.target_addr = (ip, port)
        # 创建 UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_angle(self, pan, tilt):
        """
        发送云台角度
        :param pan: 左右角度 (int)
        :param tilt: 上下角度 (int)
        """
        try:
            # 协议格式：P90,T90
            msg = f"P{int(pan)},T{int(tilt)}"
            # UDP 发送不需要 connect，直接 sendto
            self.sock.sendto(msg.encode('utf-8'), self.target_addr)
        except Exception as e:
            # UDP 发送极少报错，除非网卡掉了，这里简单打印一下即可
            print(f"[Gimbal Error] {e}")

    def close(self):
        self.sock.close()




# 定义混合服务类，用于同时管理串口和 TCP
class HybridService:
    def __init__(self, log_callback=None):
        # 实例化内部的串口服务
        self.serial = SerialService(log_callback)
        # 实例化内部的 TCP 服务
        self.net_service = UDPService(log_callback) 

    @property
    def is_connected(self):
        # 这是一个属性方法：只要串口或 TCP 有一个连着，就认为整体是连接状态
        return self.serial.is_connected or self.net_service.is_connected

    def get_ports(self):
        # 获取所有物理串口列表
        p = self.serial.get_ports()
        # 在列表末尾添加一个默认的 IP 地址项（方便 UI 列表选择）
        p.append("192.168.10.110:8080")
        # 返回整合后的列表
        return p

    def connect(self, target):
        # 如果输入的目标字符串包含冒号，判定为网络连接（IP:PORT）
        if ":" in target:
            try:
                # 以冒号分割出 IP 地址和端口号
                ip, port = target.split(":")
                # 调用 TCP 连接方法
                return self.net_service.connect(ip.strip(), port.strip())
            except: 
                # 格式不对返回错误
                return False, "Format Error"
        else:
            # 如果没有冒号，判定为串口连接
            return self.serial.connect(target)

    def disconnect(self):
        # 同时断开串口和 TCP 连接
        self.serial.disconnect()
        self.net_service.disconnect()
        # 返回关闭状态
        return "CLOSED"

    def send(self, data_str):
        # 如果串口已连，向串口发送一份数据
        if self.serial.is_connected: self.serial.send(data_str)
        # 如果 TCP 已连，向网络发送一份数据
        if self.net_service.is_connected: self.net_service.send(data_str)