"""
uiautomator2控制器模块。
提供通过uiautomator2控制Android设备的功能。
"""
import time
from typing import Tuple, Optional

import numpy as np
import uiautomator2 as u2
from adbutils.errors import AdbError
from lxml import etree

from module.base.utils import *
from module.device.controllers.base import DeviceController
from module.device.method.utils import (ImageTruncated, PackageNotInstalled, RETRY_TRIES,
                                      handle_adb_error, handle_unknown_host_service,
                                      possible_reasons, retry_sleep)
from module.exception import RequestHumanTakeover
from module.logger import logger


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
                    self.adb_reconnect()
            except JSONDecodeError as e:
                logger.error(e)
                def init():
                    self.install_uiautomator2()
            except AdbError as e:
                if handle_adb_error(e):
                    def init():
                        self.adb_reconnect()
                elif handle_unknown_host_service(e):
                    def init():
                        self.adb_start_server()
                        self.adb_reconnect()
                else:
                    break
            except RuntimeError as e:
                if handle_adb_error(e):
                    def init():
                        self.adb_reconnect()
                else:
                    break
            except AssertionError as e:
                logger.exception(e)
                possible_reasons(
                    'If you are using BlueStacks or LD player or WSA, '
                    'please enable ADB in the settings of your emulator'
                )
                break
            except PackageNotInstalled as e:
                logger.error(e)
                def init():
                    self.detect_package()
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


class UiautomatorController(DeviceController):
    """
    uiautomator2控制器。
    提供通过uiautomator2控制Android设备的功能。
    """
    
    def __init__(self, config):
        """
        初始化uiautomator2控制器。
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        self.u2 = None
        
    def connect(self) -> bool:
        """
        连接设备。
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self.u2 = u2.connect(self.config.Emulator_Serial)
            return True
        except Exception as e:
            logger.error(f'Failed to connect to device: {e}')
            return False
            
    def disconnect(self) -> None:
        """
        断开设备连接。
        """
        if self.u2:
            self.u2 = None
            
    @retry
    def click(self, x: int, y: int) -> None:
        """
        执行点击操作。
        
        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
        """
        self.u2.click(x, y)
        
    @retry
    def long_click(self, x: int, y: int, duration: float = 1.0) -> None:
        """
        执行长按操作。
        
        Args:
            x: 长按位置的x坐标
            y: 长按位置的y坐标
            duration: 长按持续时间（秒）
        """
        self.u2.long_click(x, y, duration=duration)
        
    @retry
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
        self.u2.swipe(x1, y1, x2, y2, duration=duration)
        
    @retry
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
        self.u2.drag(x1, y1, x2, y2, duration=duration)
        
    @retry
    def screenshot(self) -> np.ndarray:
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 屏幕截图数据
        """
        image = self.u2.screenshot(format='raw')
        image = np.frombuffer(image, np.uint8)
        if image is None:
            raise ImageTruncated('Empty image after reading from buffer')

        image = cv2.imdecode(image, cv2.IMREAD_COLOR)
        if image is None:
            raise ImageTruncated('Empty image after cv2.imdecode')

        cv2.cvtColor(image, cv2.COLOR_BGR2RGB, dst=image)
        if image is None:
            raise ImageTruncated('Empty image after cv2.cvtColor')

        return image
        
    @retry
    def get_resolution(self) -> Tuple[int, int]:
        """
        获取设备分辨率。
        
        Returns:
            Tuple[int, int]: (宽度, 高度)
        """
        info = self.u2.http.get('/info').json()
        w, h = info['display']['width'], info['display']['height']
        rotation = self.get_orientation()
        if (w > h) != (rotation % 2 == 1):
            w, h = h, w
        return w, h
        
    @retry
    def app_start(self, package_name: str) -> bool:
        """
        启动应用。
        
        Args:
            package_name: 应用包名
            
        Returns:
            bool: 是否成功启动
        """
        try:
            self.u2.app_start(package_name)
            return True
        except Exception as e:
            logger.error(f'Failed to start app {package_name}: {e}')
            return False
            
    @retry
    def app_stop(self, package_name: str) -> None:
        """
        停止应用。
        
        Args:
            package_name: 应用包名
        """
        self.u2.app_stop(package_name)
        
    def release(self) -> None:
        """
        释放资源。
        """
        self.disconnect() 