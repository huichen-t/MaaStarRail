# python -m pip install maafw
# 导入MAA框架的主要模块
from maa.tasker import Tasker  # 任务调度器
from maa.toolkit import Toolkit  # 工具集，包含ADB等工具
from maa.context import Context  # 上下文对象
from maa.resource import Resource  # 资源管理
from maa.controller import AdbController  # ADB控制器
from maa.custom_action import CustomAction  # 自定义动作基类
from maa.custom_recognition import CustomRecognition  # 自定义识别基类
from maa.notification_handler import NotificationHandler, NotificationType  # 通知处理器及类型

# 实例化资源对象，用于注册自定义动作和识别
resource = Resource()


def main():
    # 用户路径和资源路径
    user_path = "./"
    resource_path = "./resource"

    # 初始化工具选项
    Toolkit.init_option(user_path)

    # 加载资源包，并等待加载完成
    res_job = resource.post_bundle(resource_path)
    res_job.wait()
    
    # 查找ADB设备，如果未找到则提示并退出
    adb_devices = Toolkit.find_adb_devices()
    if not adb_devices:
        print("No ADB device found.")
        exit()

    # 这里只用第一个ADB设备进行演示
    device = adb_devices[0]
    controller = AdbController(
        adb_path=device.adb_path,  # ADB路径
        address=device.address,  # 设备地址
        screencap_methods=device.screencap_methods,  # 截图方法
        input_methods=device.input_methods,  # 输入方法
        config=device.config,  # 设备配置
    )
    # 建立与设备的连接
    controller.post_connection().wait()




if __name__ == "__main__":
    # 程序入口，执行main函数
    main()
