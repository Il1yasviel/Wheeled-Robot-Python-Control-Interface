import socket
import sys

# ==========================================
#  请填入你在 STM32 串口看到的 IP 地址
# ==========================================
TARGET_IP = "192.168.10.111"  # <--- 修改这里！！！
TARGET_PORT = 8080
# ==========================================

def main():
    print(f"[-] 正在尝试连接小车: {TARGET_IP}:{TARGET_PORT} ...")
    
    try:
        # 1. 创建 TCP 套接字
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(5) # 设置5秒超时，防止连不上一直卡住
        
        # 2. 连接服务器
        client.connect((TARGET_IP, TARGET_PORT))
        print("[+] 连接成功！")
        
        # 3. 发送一条测试指令
        print("[-] 发送测试指令: M100")
        client.send("M100".encode('utf-8'))
        
        print("\n[INFO] 请输入指令 (输入 'q' 退出):")
        print("       例如: T50 (转向), S (停止), A1,90 (舵机)")

        while True:
            # 获取键盘输入
            msg = input("Cmd >> ")
            
            if msg.lower() == 'q':
                break
            
            if not msg:
                continue

            # 发送指令
            try:
                # 这里的 .encode 转成字节流发送
                client.send(msg.encode('utf-8'))
                print(f"    >>> 已发送: {msg}")
            except Exception as e:
                print(f"[!] 发送失败: {e}")
                break

    except ConnectionRefusedError:
        print("[x] 连接被拒绝！请检查：")
        print("    1. STM32 是否已经打印 'TCP Server Started'？")
        print("    2. IP 地址是否填对了？")
    except socket.timeout:
        print("[x] 连接超时！请检查电脑和小车是否在同一个 WiFi 下。")
    except Exception as e:
        print(f"[x] 发生错误: {e}")
    finally:
        client.close()
        print("[-] 连接已关闭")

if __name__ == "__main__":
    main()