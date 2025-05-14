"""
设备控制器基类模块。
定义所有设备控制器必须实现的接口。
"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Any

import numpy as np


class DeviceController(ABC):
    """
    设备控制器基类。
    定义所有设备控制器必须实现的接口。
    """
    
    def __init__(self, config: Any):
        """
        初始化控制器。
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.device = None
        
    @abstractmethod
    def connect(self) -> bool:
        """
        连接设备。
        
        Returns:
            bool: 连接是否成功
        """
        pass
        
    @abstractmethod
    def disconnect(self) -> None:
        """
        断开设备连接。
        """
        pass
        
    @abstractmethod
    def click(self, x: int, y: int) -> None:
        """
        执行点击操作。
        
        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
        """
        pass
        
    @abstractmethod
    def long_click(self, x: int, y: int, duration: float = 1.0) -> None:
        """
        执行长按操作。
        
        Args:
            x: 长按位置的x坐标
            y: 长按位置的y坐标
            duration: 长按持续时间（秒）
        """
        pass
        
    @abstractmethod
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.1) -> None:
        """
        执行滑动操作。
        
        Args:
            x1: 起始点x坐标
            y1: 起始点y坐标
            x2: 结束点x坐标
            y2: 结束点y坐标
            duration: 滑动持续时间（秒）
        """
        pass
        
    @abstractmethod
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.1) -> None:
        """
        执行拖拽操作。
        
        Args:
            x1: 起始点x坐标
            y1: 起始点y坐标
            x2: 结束点x坐标
            y2: 结束点y坐标
            duration: 拖拽持续时间（秒）
        """
        pass
        
    @abstractmethod
    def screenshot(self) -> np.ndarray:
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 屏幕截图数据
        """
        pass
        
    @abstractmethod
    def get_resolution(self) -> Tuple[int, int]:
        """
        获取设备分辨率。
        
        Returns:
            Tuple[int, int]: (宽度, 高度)
        """
        pass
        
    @abstractmethod
    def app_start(self, package_name: str) -> bool:
        """
        启动应用。
        
        Args:
            package_name: 应用包名
            
        Returns:
            bool: 是否成功启动
        """
        pass
        
    @abstractmethod
    def app_stop(self, package_name: str) -> None:
        """
        停止应用。
        
        Args:
            package_name: 应用包名
        """
        pass
        
    @abstractmethod
    def release(self) -> None:
        """
        释放资源。
        """
        pass 