"""
aScreenCap截图模块。
提供高效的屏幕截图功能，使用aScreenCap工具进行截图。
相比ADB screencap命令，aScreenCap具有以下优势：
1. 更快的截图速度
2. 更低的CPU占用
3. 更小的内存占用
4. 支持压缩传输

与adb.py的关系：
- adb.py提供基础的ADB操作接口
- ascreencap.py在adb.py的基础上封装了专门的截图功能
- 两者都继承自Connection类，共享基础的设备连接功能
- 当adb.py的screencap命令无法满足需求时，可以使用ascreencap.py作为替代方案
"""

import os
from typing import Optional, Dict, Any

import numpy as np

from module.device.components.device_connection import DeviceConnection
from module.device.components.command_executor import CommandExecutor
from module.device.components.screenshot import ScreenshotComponent
from module.device.method.utils import ImageTruncated
from module.exception import RequestHumanTakeover
from module.base.logger import logger


class AScreenCap:
    """
    aScreenCap截图类。
    提供高效的屏幕截图功能。
    """
    def __init__(self, connection: DeviceConnection, executor: CommandExecutor, config: Dict[str, Any]):
        self.connection = connection
        self.executor = executor
        self.config = config
        self.screenshot = ScreenshotComponent(connection, executor, config)

    def init_screenshot_tool(self):
        """
        初始化截图工具。
        根据设备架构和Android版本选择合适的截图工具。
        
        Raises:
            RequestHumanTakeover: 当没有合适的截图工具版本时抛出
        """
        self.screenshot.init_screenshot_tool()

    def uninstall_screenshot_tool(self):
        """卸载截图工具"""
        self.screenshot.uninstall_screenshot_tool()

    def screenshot(self) -> np.ndarray:
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 截图数据
            
        Raises:
            RequestHumanTakeover: 当截图失败时抛出
        """
        return self.screenshot.screenshot()

    def screenshot_nc(self) -> np.ndarray:
        """
        使用netcat获取屏幕截图。
        
        Returns:
            np.ndarray: 截图数据
            
        Raises:
            RequestHumanTakeover: 当截图失败时抛出
        """
        return self.screenshot.screenshot_nc()
