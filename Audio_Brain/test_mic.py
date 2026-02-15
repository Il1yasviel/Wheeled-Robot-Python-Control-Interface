import pyaudio
import numpy as np

def list_microphones():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    
    print("--- 可用的音频输入设备 ---")
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            print(f"ID {i}: {p.get_device_info_by_host_api_device_index(0, i).get('name')}")
    print("-------------------------")
    p.terminate()

def test_recording():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    print("\n正在录音测试（请说话）... 按 Ctrl+C 停止")
    try:
        while True:
            data = stream.read(CHUNK)
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.linalg.norm(audio_data) / 10
            print(f"\r当前音量: {'|' * int(volume/10)} ({int(volume)})", end="")
    except KeyboardInterrupt:
        pass
    finally:
        print("\n测试结束")
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    list_microphones()
    test_recording()
