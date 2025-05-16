"""
截图方法基类模块。
定义所有截图方法必须实现的接口。
"""

from abc import ABC, abstractmethod
import numpy as np


class ScreenshotMethod(ABC):
    """
    截图方法基类。
    所有具体的截图方法都必须继承此类并实现其方法。
    """
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        检查此截图方法是否可用。
        
        Returns:
            bool: 是否可用
        """
        pass
    
    @abstractmethod
    def screenshot(self) -> np.ndarray:
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 截图图像数据
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        获取截图方法名称。
        
        Returns:
            str: 方法名称
        """
        pass 