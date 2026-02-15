import os
import pyaudio
# === 【新增】解决 OpenMP 冲突错误 ===
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
# ===================================
import numpy as np
from faster_whisper import WhisperModel
import time

class VoiceBrain:
    def __init__(self):
        # 1. 配置参数
        self.WAKE_WORDS = ["小R", "小r", "识别", "看到", "看"]  # 唤醒词列表
        self.VAD_THRESHOLD = 500      # 【重要】静音阈值，根据上一步测试调整！
        self.SILENCE_LIMIT = 1.5      # 说话停顿超过 1.5 秒视为结束
        self.MODEL_SIZE = "medium"    # 3060 6G 显存可以用 small 或 medium
        
        # 2. 加载模型 (自动下载到 ./models 文件夹)
        print(f"正在加载 Whisper {self.MODEL_SIZE} 模型到 GPU (RTX 3060)...")
        # download_root 指定模型下载路径，方便管理
        self.model = WhisperModel(self.MODEL_SIZE, device="cuda", compute_type="float16", download_root="./models")
        print(">>> 模型加载完毕！语音系统就绪。")

    def process_audio_stream(self):
        # 音频流配置
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000 # Whisper 推荐采样率

        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

        print(f"\n监听中... (请说出包含 '{self.WAKE_WORDS}' 的句子)")

        frames = []
        is_speaking = False
        silence_start_time = None

        while True:
            try:
                # 读取麦克风数据
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.linalg.norm(audio_data) / 10  # 计算音量

                # === 简单的 VAD 状态机 ===
                
                # 状态 1: 正在说话
                if volume > self.VAD_THRESHOLD:
                    if not is_speaking:
                        print("检测到人声，开始录音...", end="\r")
                        is_speaking = True
                    frames.append(audio_data) # 存入 float32 数组或保持 int16
                    silence_start_time = None # 重置静音计时器
                
                # 状态 2: 正在说话，但突然停顿了
                elif is_speaking:
                    frames.append(audio_data) # 停顿时的背景音也录进去，让语音更自然
                    
                    if silence_start_time is None:
                        silence_start_time = time.time()
                    
                    # 如果停顿时间超过设定值，认为这一句话说完了
                    if time.time() - silence_start_time > self.SILENCE_LIMIT:
                        print("\n语音结束，正在识别...")
                        is_speaking = False
                        
                        # === 开始识别 (核心逻辑) ===
                        self.transcribe_and_check(frames)
                        
                        # 重置
                        frames = []
                        print("\n监听中...")

            except KeyboardInterrupt:
                break

        stream.stop_stream()
        stream.close()
        p.terminate()

    def transcribe_and_check(self, frames):
        # 1. 数据转换：将 List[numpy] 转换为单个 float32 numpy 数组
        # Faster-Whisper 可以直接吃 numpy 数组，不需要存成 wav 文件，速度更快！
        audio_data = np.concatenate(frames)
        
        # 归一化到 [-1, 1] 之间 (int16 范围是 -32768 到 32767)
        audio_float32 = audio_data.astype(np.float32) / 32768.0

        # 2. 模型推理
        segments, info = self.model.transcribe(audio_float32, beam_size=5, language="zh")

        # 3. 获取文本
        full_text = ""
        for segment in segments:
            full_text += segment.text

        # 去除空格和标点（可选，为了更好匹配）
        clean_text = full_text.strip()
        print(f"【识别结果】: {clean_text}")

        # 4. 关键词触发
        triggered = False
        for word in self.WAKE_WORDS:
            if word in clean_text:
                triggered = True
                break
        
        if triggered:
            print(f"🚀🚀🚀 触发唤醒词！正在执行指令... [内容: {clean_text}]")
            # TODO: 未来这里会发送信号给 YOLO 线程
        else:
            print("--- 无效指令 (未包含唤醒词) ---")

if __name__ == "__main__":
    brain = VoiceBrain()
    brain.process_audio_stream()