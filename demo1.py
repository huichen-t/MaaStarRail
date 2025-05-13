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

    # 创建任务调度器
    tasker = Tasker()
    # tasker = Tasker(notification_handler=MyNotificationHandler())  # 可选：自定义通知处理器
    # 绑定资源和控制器
    tasker.bind(resource, controller)

    # 检查MAA是否初始化成功
    if not tasker.inited:
        print("Failed to init MAA.")
        exit()

    # 示例：自定义流水线覆盖配置
    pipeline_override = {
        "MyCustomEntry": {"action": "custom", "custom_action": "MyCustomAction"},
    }

    # 另一种注册自定义识别/动作的方法
    # resource.register_custom_recognition("My_Recongition", MyRecongition())
    # resource.register_custom_action("My_CustomAction", MyCustomAction())

    # 提交任务并等待完成，获取任务详情
    task_detail = tasker.post_task("MyCustomEntry", pipeline_override).wait().get()
    # 可以在此处对task_detail做进一步处理


# 通过装饰器自动注册自定义识别类，也可以手动注册
@resource.custom_recognition("MyRecongition")
class MyRecongition(CustomRecognition):
    """
    自定义识别类，继承自CustomRecognition。
    """
    def analyze(
        self,
        context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        # 使用OCR识别，指定ROI区域
        reco_detail = context.run_recognition(
            "MyCustomOCR",
            argv.image,
            pipeline_override={"MyCustomOCR": {"recognition": "OCR", "roi": [100, 100, 200, 300]}},
        )

        # 直接修改全局流水线配置，影响整个任务
        context.override_pipeline({"MyCustomOCR": {"roi": [1, 1, 114, 514]}})
        # context.run_recognition ...

        # 克隆一个新的上下文，仅影响本次识别
        new_context = context.clone()
        new_context.override_pipeline({"MyCustomOCR": {"roi": [100, 200, 300, 400]}})
        reco_detail = new_context.run_recognition("MyCustomOCR", argv.image)

        # 发送点击操作
        click_job = context.tasker.controller.post_click(10, 20)
        click_job.wait()

        # 指定下一个节点的候选列表
        context.override_next(argv.node_name, ["TaskA", "TaskB"])

        # 返回识别结果，包含识别框和详细信息
        return CustomRecognition.AnalyzeResult(
            box=(0, 0, 100, 100), detail="Hello World!"
        )


class MyNotificationHandler(NotificationHandler):
    """
    自定义通知处理器，重写各类通知回调方法。
    """
    def on_resource_loading(
        self,
        noti_type: NotificationType,
        detail: NotificationHandler.ResourceLoadingDetail,
    ):
        print(f"on_resource_loading: {noti_type}, {detail}")

    def on_controller_action(
        self,
        noti_type: NotificationType,
        detail: NotificationHandler.ControllerActionDetail,
    ):
        print(f"on_controller_action: {noti_type}, {detail}")

    def on_tasker_task(
        self, noti_type: NotificationType, detail: NotificationHandler.TaskerTaskDetail
    ):
        print(f"on_tasker_task: {noti_type}, {detail}")

    def on_node_next_list(
        self,
        noti_type: NotificationType,
        detail: NotificationHandler.NodeNextListDetail,
    ):
        print(f"on_node_next_list: {noti_type}, {detail}")

    def on_node_recognition(
        self,
        noti_type: NotificationType,
        detail: NotificationHandler.NodeRecognitionDetail,
    ):
        print(f"on_node_recognition: {noti_type}, {detail}")

    def on_node_action(
        self, noti_type: NotificationType, detail: NotificationHandler.NodeActionDetail
    ):
        print(f"on_node_action: {noti_type}, {detail}")


# 通过装饰器自动注册自定义动作类，也可以手动注册
@resource.custom_action("MyCustomAction")
class MyCustomAction(CustomAction):
    """
    自定义动作类，继承自CustomAction。
    """
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        """
        :param argv: 动作参数
        :param context: 运行上下文
        :return: 是否执行成功。-参考流水线协议 `on_error`
        """
        print("MyCustomAction is running!")
        return True


if __name__ == "__main__":
    # 程序入口，执行main函数
    main()
