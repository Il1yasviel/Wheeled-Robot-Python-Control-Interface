import socket
import threading
import time

class SensorService(threading.Thread):
    def __init__(self, ip, port, callback):
        super().__init__()
        self.ip = ip
        self.port = int(port)
        self.callback = callback # 回调函数，用于把数据传回 Controller
        self.running = True
        self.sock = None
    #重写父类的函数，当线程对象调用start函数后，就会间接调用这个run函数
    def run(self):
        while self.running:
            try:
                # 1. 尝试连接 (如果没有连接上)
                if self.sock is None:
                    print(f"[SENSOR] Connecting to {self.ip}:{self.port}...")
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(3) # 设置超时，防止卡死
                    self.sock.connect((self.ip, self.port))
                    print("[SENSOR] Connected!")

                # 2. 接收数据
                # 假设开发板发过来的是: "Humi: 55% Temp: 9C"
                data = self.sock.recv(1024) 
                
                if not data:
                    # 如果收到空数据，说明连接断了
                    print("[SENSOR] Disconnected by server.")
                    self.close_socket()
                    time.sleep(2) # 等一会再重连
                    continue

                # 3. 解码并通知主程序
                text = data.decode('utf-8').strip()
                # 调用回调函数，把文本传出去
                if self.callback:
                    self.callback(text)

            except Exception as e:
                # print(f"[SENSOR] Error: {e}")
                self.close_socket()
                time.sleep(2) # 出错后等待重连

    def close_socket(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

    def stop(self):
        self.running = False
        self.close_socket()