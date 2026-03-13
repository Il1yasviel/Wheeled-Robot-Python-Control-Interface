# -*- coding: utf-8 -*-
import socket
import threading
import tempfile
import os
import glob
import time
import base64
import json
import requests
import re
from faster_whisper import WhisperModel

class AIBridgeService:
    def __init__(self, ui_chat_callback, save_audio_callback):
        """
        :param ui_chat_callback: 往界面聊天框塞文字的函数
        :param save_audio_callback: 把接收到的AI音频保存的函数
        """
        self.ui_chat_callback = ui_chat_callback
        self.save_audio_callback = save_audio_callback
        
        self.api_url = "http://127.0.0.1:8000/chat_stream" # 刚才搭好的黑盒大模型服务
        self.vision_dir = "vision_memory" # 必须和视觉服务保存的目录一致

        # 1. 初始化听觉神经 (语音转文字)
        print("[AI Bridge] 正在加载 STT 模型...")
        self.stt_model = WhisperModel("base", device="cpu", compute_type="int8")
        
        # 2. 启动 Socket 服务器，专门等待 RK3506 传音频过来
        self.audio_port = 9000  # RK3506 发送音频的目标端口
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("0.0.0.0", self.audio_port))
        self.server_socket.listen(5)
        
        print(f"[AI Bridge] 监听服务已启动，端口: {self.audio_port}，等待 RK3506 语音数据...")
        threading.Thread(target=self._accept_connections, daemon=True).start()

    def _accept_connections(self):
        """后台死循环：接收 RK3506 的连接"""
        while True:
            try:
                client_sock, addr = self.server_socket.accept()
                print(f"[AI Bridge] 接收到来自 {addr} 的音频连接")
                # 开个新线程去接收数据，不阻塞下一个连接
                threading.Thread(target=self._handle_rk3506_audio, args=(client_sock,), daemon=True).start()
            except Exception as e:
                print(f"[AI Bridge] Socket 接收异常: {e}")

    def _handle_rk3506_audio(self, client_sock):
        """处理接收到的二进制音频流，并走完整个 AI 流程"""
        try:
            # 1. 接收 RK3506 传来的音频文件
            audio_bytes = b""
            while True:
                chunk = client_sock.recv(4096)
                if not chunk: break # 当客户端调用 shutdown(SHUT_WR) 时，这里会收到空字节并跳出
                audio_bytes += chunk
            
            # 注意：这里千万不要 client_sock.close()，因为我们还要用它把声音发回去！

            if len(audio_bytes) < 100: 
                client_sock.close()
                return 

            # 2. 将音频存入临时文件，交给 Whisper 识别
            print(f"[AI Bridge] 成功接收音频 {len(audio_bytes)} 字节，正在识别...")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name
            
            segments, _ = self.stt_model.transcribe(tmp_path, language="zh")
            user_text = "".join([s.text for s in segments]).strip()
            os.remove(tmp_path)

            if not user_text:
                print("[AI Bridge] 啥也没听清")
                client_sock.close()
                return
            
            print(f"[AI Bridge] 识别结果: {user_text}")
            self.ui_chat_callback("User", f"[User]: {user_text}\n")
            
            # 3. 关键字正则匹配，判断是否需要调用视觉截图
            needs_vision = any(keyword in user_text for keyword in ["你看", "这是什么", "看到了什么", "图"])
            image_base64 = ""
            if needs_vision:
                print("[AI Bridge] 触发视觉指令，正在提取最新截图...")
                latest_image = self._get_latest_frame()
                if latest_image:
                    with open(latest_image, "rb") as img_f:
                        image_base64 = base64.b64encode(img_f.read()).decode('utf-8')
                    self.ui_chat_callback("System", "[System] 已附加最新视觉截图发送...\n")
            
            # 4. 把数据和【未关闭的 Socket】一起传给发送函数
            self._send_to_ai_server(user_text, image_base64, client_sock)

        except Exception as e:
            print(f"[AI Bridge] 处理流程报错: {e}")
            client_sock.close()

    def _get_latest_frame(self):
        """从视觉缓存目录拿最新的一张图"""
        files = sorted(glob.glob(os.path.join(self.vision_dir, "*.jpg")), key=os.path.getmtime)
        if files:
            return files[-1] # 返回时间最新的文件路径
        return None

    def _send_to_ai_server(self, text, image_base64, client_sock):
        """将组合好的数据发给 API 服务，并将接收到的音频发回 RK3506"""
        payload = {
            "text": text,
            "image_base64": image_base64,
            "audio_base64": "" 
        }

        try:
            self.ui_chat_callback("AI", "[AI]: ", end="")
            response = requests.post(self.api_url, json=payload, stream=True)
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode('utf-8'))
                    
                    if data["type"] == "text":
                        self.ui_chat_callback("AI", data["content"])
                        
                    elif data["type"] == "audio":
                        audio_b64 = data["content"]
                        audio_bytes = base64.b64decode(audio_b64)
                        
                        # 1. 保存到 PC 本地
                        self.save_audio_callback(audio_bytes)
                        
                        # 2. 【核心通讯协议】：发回给 RK3506
                        # 先发 4 个字节表示这个 WAV 文件有多大，再发真实的音频数据
                        length_prefix = len(audio_bytes).to_bytes(4, byteorder='big')
                        client_sock.sendall(length_prefix + audio_bytes)

            self.ui_chat_callback("AI", "\n")
            
        except Exception as e:
            self.ui_chat_callback("System", f"\n[System] 连接 AI 大脑失败: {e}\n")
        finally:
            # 所有的对话都发完了，安全关闭连接
            client_sock.close()
            print("[AI Bridge] 当前对话结束，已断开与 RK3506 的连接。")