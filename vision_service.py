# -*- coding: utf-8 -*-
import cv2
import time
import threading
from ultralytics import YOLO

class VisionService(threading.Thread):
    def __init__(self, stream_url, callback_func):
        """
        视觉处理服务类 (基于多线程)
        :param stream_url: 视频流的地址（如 http://IP:8080/?action=stream 或 摄像头索引 0）
        :param callback_func: 这是一个回调函数，由 Controller 提供，用于把处理好的画面送回给 UI 显示
        """
        # 必须调用父类 threading.Thread 的初始化方法
        super().__init__()
        
        # 保存传入的视频流地址
        self.stream_url = stream_url
        # 保存回调函数接口
        self.callback = callback_func
        # 线程运行状态控制位，设置为 True 时循环开始，False 时循环停止
        self.running = False 
        
        # --- YOLO 深度学习模型初始化 ---
        print("[VISION] 正在加载 YOLO 识别模型，请稍候...")
        try:
            # 加载预训练模型文件 (yolov8n.pt 是轻量化版本，适合实时推理)
            self.model = YOLO('./YOLOV8_recognition/model/yolov8n.pt').to('cuda')
            
            # 性能优化：尝试将模型移动到 GPU (CUDA) 运行
            # 如果你的电脑没配置好 CUDA 环境，这行代码会自动降级到 CPU 运行
            # self.model.to('cuda') 
            
            print(f"[VISION] 模型加载完成，当前运行设备: {self.model.device}")
        except Exception as e:
            # 如果路径不对或显卡驱动有问题，会捕获异常并提示
            print(f"[VISION] 模型加载失败，请检查路径或环境: {e}")
            self.model = None

    def run(self):
        """
        线程启动后 (start()) 自动执行的逻辑主循环
        """
        self.running = True
        
        # 1. 初始化 OpenCV 的视频捕获对象
        cap = cv2.VideoCapture(self.stream_url)
        
        # 用于记录上一帧的时间戳，辅助计算 FPS (每秒帧数)
        prev_time = 0

        print(f"[VISION] 视频流线程已启动，正在连接: {self.stream_url}")
        
        # 进入核心处理死循环，直到 self.running 被外部改为 False
        while self.running:
            # 2. 从视频流中抓取一帧图像
            # success: 布尔值，代表是否抓取成功
            # frame: 抓取到的原始图像数据 (BGR 格式的 numpy 数组)
            success, frame = cap.read()

            if success:
                # --- [情况 A] 图像抓取成功 ---
                final_frame = None  # 最终要显示的图像变量
                
                # 3. 执行 YOLO 目标检测
                if self.model:
                    # source: 待检测的图像
                    # conf: 置信度阈值，0.5 表示识别概率大于 50% 才会显示结果
                    # classes: 类别过滤，[0] 通常在官方模型里代表 "Person" (人)
                    # verbose=False: 关闭 YOLO 在控制台的每一帧输出，保持终端整洁
                    results = self.model.predict(source=frame, save=False, conf=0.5, classes=[0], verbose=False)
                    
                    # 使用 results[0].plot() 将检测到的红框、标签直接画在图像上
                    # 它返回的也是 BGR 格式的图像数据
                    final_frame = results[0].plot()
                else:
                    # 如果模型加载失败，则直接使用原始画面，不进行识别
                    final_frame = frame

                # 4. 实时计算 FPS (帧率)
                curr_time = time.time()
                # 计算两次循环之间的时间差，取倒数即为 FPS
                fps = 1 / (curr_time - prev_time) if prev_time > 0 else 0
                prev_time = curr_time
                # 格式化显示文字
                fps_text = f"FPS: {int(fps)}"
                
                # 5. 通过回调函数，将处理好的【图像数据】和【FPS文字】推送给 Controller，再转交给 View
                if self.callback:
                    self.callback(final_frame, fps_text)

            else:
                # --- [情况 B] 图像抓取失败 (通常是网络断了或摄像头掉线) ---
                # 6. 尝试重新打开连接，防止程序直接崩溃
                try:
                    cap.open(self.stream_url)
                except Exception:
                    pass
                
                # 失败时适当休眠，避免死循环导致 CPU 占用率过高
                time.sleep(0.2) 
            
        # 7. 当 self.running 为 False，退出循环，释放硬件资源
        cap.release()
        print("[VISION] 视频服务已安全停止并释放资源。")

    def stop(self):
        """
        外部调用的停止接口
        Controller 在关闭窗口时会调用此函数来结束子线程
        """
        self.running = False