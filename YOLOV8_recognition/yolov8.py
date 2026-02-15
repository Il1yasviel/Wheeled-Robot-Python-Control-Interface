from ultralytics import YOLO
import cv2
import torch


print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 是否可用: {torch.cuda.is_available()}")
print(f"CUDA 版本: {torch.version.cuda}")
print(f"显卡型号: {torch.cuda.get_device_name(0)}")

# 1. 加载模型
# 第一次运行时，它会自动从官网下载 'yolov8n.pt' 模型文件到当前目录
print("正在加载模型，首次运行会自动下载权重文件...")
#model = YOLO('yolov8n.pt') 
# 强制移动到 GPU
model = YOLO('./YOLOV8_recognition/model/yolov8n.pt').to('cuda')
print(f"当前模型运行在: {model.device}") # 查看是 'cpu' 还是 'cuda:0'

# 2. 打开电脑默认摄像头 (索引通常为0)
#cap = cv2.VideoCapture(0)

# 2. 连接开发板的视频流
# 请确保你的电脑能 ping 通 192.168.10.110
stream_url = "http://192.168.10.114:8080/?action=stream"
cap = cv2.VideoCapture(stream_url)

# 检查摄像头是否成功打开
if not cap.isOpened():
    print("无法打开摄像头，请检查连接。")
    exit()

print("摄像头已启动，按 'q' 键退出。")

while True:
    # 读取一帧画面
    success, frame = cap.read()
    if not success:
        print("无法读取画面。")
        break

    # 3. 使用YOLOv8进行预测
    # conf=0.5 表示只显示置信度大于0.5的结果
    results = model.predict(source=frame, save=False, conf=0.5, classes=[0], verbose=False)
    
    # classes=[0] 意思是指只检测 "Person" (人) 这一类，忽略汽车、猫狗等其他物体
    # 如果你想检测所有物体，可以去掉 classes=[0]

    # 4. 将检测结果绘制在图像上
    annotated_frame = results[0].plot()

    # 5. 显示画面
    cv2.imshow("YOLOv8 Real-time Detection", annotated_frame)

    # 按下 'q' 键退出循环
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 释放资源
cap.release()
cv2.destroyAllWindows()