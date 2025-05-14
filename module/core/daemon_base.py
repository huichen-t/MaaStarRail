"""
守护进程基类模块，提供基础功能支持。
"""

from module.base.base import ModuleBase


class DaemonBase(ModuleBase):
    """
    守护进程基类，继承自ModuleBase
    
    用于实现各种守护进程功能，如性能测试、设备监控等。
    在初始化时会禁用设备卡死检测，以避免在长时间运行的任务中误判。
    """

    def __init__(self, *args, **kwargs):
        """
        初始化守护进程基类
        
        Args:
            *args: 传递给父类的位置参数
            **kwargs: 传递给父类的关键字参数
        """
        super().__init__(*args, **kwargs)
        # 禁用设备卡死检测，避免在长时间运行的任务中误判
        self.device.disable_stuck_detection()
