# 导入系统模块
import sys

# 导入MAA框架相关模块
from maa.agent.agent_server import AgentServer  # 代理服务器模块
from maa.custom_recognition import CustomRecognition  # 自定义识别基类
from maa.custom_action import CustomAction  # 自定义动作基类
from maa.context import Context  # 上下文对象
from maa.toolkit import Toolkit  # 工具集


def main():
    # 初始化MAA工具选项，设置用户路径为当前目录
    Toolkit.init_option("./")

    # 从命令行参数获取socket_id
    socket_id = sys.argv[-1]

    # 启动代理服务器
    AgentServer.start_up(socket_id)
    # 等待代理服务器运行
    AgentServer.join()
    # 关闭代理服务器
    AgentServer.shut_down()


# 使用装饰器注册自定义识别类
@AgentServer.custom_recognition("MyRecongition")
class MyRecongition(CustomRecognition):
    """
    自定义识别类，用于实现特定的图像识别逻辑
    """

    def analyze(
        self,
        context: Context,  # 运行上下文
        argv: CustomRecognition.AnalyzeArg,  # 分析参数
    ) -> CustomRecognition.AnalyzeResult:
        """
        分析图像并返回识别结果
        
        Args:
            context: 运行上下文，包含任务相关信息
            argv: 分析参数，包含图像数据等
            
        Returns:
            AnalyzeResult: 包含识别框和详细信息的分析结果
        """
        # 使用OCR进行识别，指定ROI区域
        reco_detail = context.run_recognition(
            "MyCustomOCR",
            argv.image,
            pipeline_override={"MyCustomOCR": {"roi": [100, 100, 200, 300]}},
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
            box=(0, 0, 100, 100),  # 识别框坐标和大小
            detail="Hello World!"  # 识别结果详情
        )


# 使用装饰器注册自定义动作类
@AgentServer.custom_action("MyCustomAction")
class MyCustomAction(CustomAction):
    """
    自定义动作类，用于实现特定的操作逻辑
    """

    def run(
        self,
        context: Context,  # 运行上下文
        argv: CustomAction.RunArg,  # 运行参数
    ) -> bool:
        """
        执行自定义动作
        
        Args:
            context: 运行上下文，包含任务相关信息
            argv: 运行参数
            
        Returns:
            bool: 动作是否执行成功
        """
        print("MyCustomAction is running!")
        return True


# 程序入口点
if __name__ == "__main__":
    main()
