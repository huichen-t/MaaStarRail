"""
截图组件模块。
提供设备截图相关的功能，包括：
- 截图方法管理
- 截图数据处理
- 截图工具初始化
"""

import os
import time
from functools import wraps
from typing import Optional, Union, List, Dict, Any

import lz4.block
import numpy as np
from adbutils.errors import AdbError

from module.device.components.device_connection import DeviceConnection
from module.device.components.command_executor import CommandExecutor
from module.device.method.utils import (ImageTruncated, RETRY_TRIES, handle_adb_error, 
                                      handle_unknown_host_service, retry_sleep)
from module.exception import RequestHumanTakeover, ScriptError
from module.base.logger import logger


class ScreenshotError(Exception):
    """截图相关错误的异常类"""
    pass


def retry(func):
    """
    重试装饰器。
    当函数执行失败时自动重试，最多重试RETRY_TRIES次。
    
    Args:
        func: 需要重试的函数
        
    Returns:
        装饰后的函数
    """
    @wraps(func)
    def retry_wrapper(self, *args, **kwargs):
        init = None
        for _ in range(RETRY_TRIES):
            try:
                if callable(init):
                    time.sleep(retry_sleep(_))
                    init()
                return func(self, *args, **kwargs)
            except RequestHumanTakeover:
                break
            except ConnectionResetError as e:
                logger.error(e)
                def init():
                    self.connection.reconnect()
            except ScreenshotError as e:
                logger.error(e)
                def init():
                    self.init_screenshot_tool()
            except AdbError as e:
                if handle_adb_error(e):
                    def init():
                        self.connection.reconnect()
                elif handle_unknown_host_service(e):
                    def init():
                        self.connection.start_server()
                        self.connection.reconnect()
                else:
                    break
            except ImageTruncated as e:
                logger.error(e)
                def init():
                    pass
            except Exception as e:
                logger.exception(e)
                def init():
                    pass

        logger.critical(f'Retry {func.__name__}() failed')
        raise RequestHumanTakeover

    return retry_wrapper


class ScreenshotComponent:
    """
    截图组件类。
    提供设备截图相关的功能。
    """
    def __init__(self, connection: DeviceConnection, executor: CommandExecutor, config: Dict[str, Any]):
        self.connection = connection
        self.executor = executor
        self.config = config
        self._bytepointer = 0
        self._screenshot_methods = [0, 1, 2]  # 截图方法列表
        self._screenshot_methods_fixed = [0, 1, 2]  # 固定的截图方法列表
        self._screenshot_tool_available = True  # 截图工具是否可用

    def init_screenshot_tool(self):
        """
        初始化截图工具。
        根据设备架构和Android版本选择合适的截图工具。
        
        Raises:
            RequestHumanTakeover: 当没有合适的截图工具版本时抛出
        """
        logger.hr('Screenshot tool init')
        self._bytepointer = 0
        self._screenshot_tool_available = True

        arc = self.connection.cpu_abi
        sdk = self.connection.sdk_ver
        logger.info(f'cpu_arc: {arc}, sdk_ver: {sdk}')

        # 根据Android版本选择对应的截图工具版本
        if sdk in range(21, 26):
            ver = "Android_5.x-7.x"
        elif sdk in range(26, 28):
            ver = "Android_8.x"
        elif sdk == 28:
            ver = "Android_9.x"
        else:
            ver = "0"
            
        filepath = os.path.join(self.config['ASCREENCAP_FILEPATH_LOCAL'], ver, arc, 'ascreencap')
        if not os.path.exists(filepath):
            self._screenshot_tool_available = False
            logger.error('No suitable version of screenshot tool available for this device, '
                        'please use other screenshot methods instead')
            raise RequestHumanTakeover

        logger.info(f'pushing {filepath}')
        self.executor.adb_push(filepath, self.config['ASCREENCAP_FILEPATH_REMOTE'])

        logger.info(f'chmod 0777 {self.config["ASCREENCAP_FILEPATH_REMOTE"]}')
        self.executor.adb_shell(['chmod', '0777', self.config['ASCREENCAP_FILEPATH_REMOTE']])

    def uninstall_screenshot_tool(self):
        """卸载截图工具"""
        logger.info('Removing screenshot tool')
        self.executor.adb_shell(['rm', self.config['ASCREENCAP_FILEPATH_REMOTE']])

    def _reposition_byte_pointer(self, byte_array: bytes) -> bytes:
        """
        重新定位字节指针。
        用于处理某些设备上出现的链接器警告问题。
        
        Args:
            byte_array: 原始字节数组
            
        Returns:
            bytes: 处理后的字节数组
            
        Raises:
            ScreenshotError: 当无法重新定位指针时抛出
        """
        while byte_array[self._bytepointer:self._bytepointer + 4] != b'BMZ1':
            self._bytepointer += 1
            if self._bytepointer >= len(byte_array):
                text = 'Repositioning byte pointer failed, corrupted screenshot data received'
                logger.warning(text)
                if len(byte_array) < 500:
                    logger.warning(f'Unexpected screenshot: {byte_array}')
                raise ScreenshotError(text)
        return byte_array[self._bytepointer:]

    def _uncompress(self, screenshot: bytes) -> bytes:
        """
        解压缩截图数据。
        
        Args:
            screenshot: 压缩的截图数据
            
        Returns:
            bytes: 解压后的截图数据
        """
        try:
            return lz4.block.decompress(screenshot)
        except Exception as e:
            logger.error(f'Failed to uncompress screenshot: {e}')
            raise ScreenshotError(f'Failed to uncompress screenshot: {e}')

    def _process_screenshot(self, screenshot: bytes) -> np.ndarray:
        """
        处理截图数据。
        
        Args:
            screenshot: 原始截图数据
            
        Returns:
            np.ndarray: 处理后的图像数据
        """
        try:
            # 重新定位字节指针
            screenshot = self._reposition_byte_pointer(screenshot)
            # 解压缩数据
            screenshot = self._uncompress(screenshot)
            # 转换为numpy数组
            return np.frombuffer(screenshot, dtype=np.uint8)
        except Exception as e:
            logger.error(f'Failed to process screenshot: {e}')
            raise ScreenshotError(f'Failed to process screenshot: {e}')

    @retry
    def screenshot(self) -> np.ndarray:
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 截图数据
            
        Raises:
            ScreenshotError: 当截图失败时抛出
        """
        try:
            result = self.executor.adb_shell([self.config['ASCREENCAP_FILEPATH_REMOTE']], stream=True)
            return self._process_screenshot(result)
        except Exception as e:
            logger.error(f'Failed to take screenshot: {e}')
            raise ScreenshotError(f'Failed to take screenshot: {e}')

    @retry
    def screenshot_nc(self) -> np.ndarray:
        """
        使用netcat获取屏幕截图。
        
        Returns:
            np.ndarray: 截图数据
            
        Raises:
            ScreenshotError: 当截图失败时抛出
        """
        try:
            result = self.executor.adb_shell_nc([self.config['ASCREENCAP_FILEPATH_REMOTE']])
            return self._process_screenshot(result)
        except Exception as e:
            logger.error(f'Failed to take screenshot with netcat: {e}')
            raise ScreenshotError(f'Failed to take screenshot with netcat: {e}') 