"""
ADB控制器模块。
提供通过ADB控制Android设备的基本功能。
"""
import time
from typing import Tuple
import numpy as np
from adbutils.errors import AdbError

from module.device.controllers.base import DeviceController
from module.device.method.utils import (ImageTruncated, PackageNotInstalled, RETRY_TRIES,
                                      handle_adb_error, handle_unknown_host_service,
                                      possible_reasons, retry_sleep)
from module.exception import RequestHumanTakeover
from module.base.logger import logger


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


class AdbController(DeviceController):
    """
    ADB控制器。
    提供通过ADB控制Android设备的基本功能。
    """
    
    def __init__(self, config):
        """
        初始化ADB控制器。
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        self.max_x = 0
        self.max_y = 0
        
    def connect(self) -> bool:
        """
        连接设备。
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 获取设备信息
            info = self.device.shell('getevent -p | grep -e "add device" -e "ABS_MT_POSITION"').strip()
            if not info:
                raise RuntimeError('No touch device found')
                
            # 解析设备信息
            for line in info.split('\n'):
                if 'ABS_MT_POSITION_X' in line:
                    self.max_x = int(line.split('max ')[1])
                elif 'ABS_MT_POSITION_Y' in line:
                    self.max_y = int(line.split('max ')[1])
                    
            return True
        except Exception as e:
            logger.error(f'Failed to connect to device: {e}')
            return False
            
    def disconnect(self) -> None:
        """
        断开设备连接。
        """
        pass
        
    @retry
    def click(self, x: int, y: int) -> None:
        """
        执行点击操作。
        
        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
        """
        self.device.shell(f'input tap {x} {y}')
        
    @retry
    def long_click(self, x: int, y: int, duration: float = 1.0) -> None:
        """
        执行长按操作。
        
        Args:
            x: 长按位置的x坐标
            y: 长按位置的y坐标
            duration: 长按持续时间（秒）
        """
        self.device.shell(f'input swipe {x} {y} {x} {y} {int(duration * 1000)}')
        
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
        self.device.shell(f'input swipe {x1} {y1} {x2} {y2} {int(duration * 1000)}')
        
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
        self.swipe(x1, y1, x2, y2, duration)
        
    @retry
    def screenshot(self) -> np.ndarray:
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 屏幕截图数据
        """
        image = self.device.screenshot()
        if image is None:
            raise ImageTruncated('Empty image after reading from buffer')
            
        return image
        
    @retry
    def get_resolution(self) -> Tuple[int, int]:
        """
        获取设备分辨率。
        
        Returns:
            Tuple[int, int]: (宽度, 高度)
        """
        return self.max_x, self.max_y
        
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
            self.device.shell(f'am start -n {package_name}/.MainActivity')
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
        self.device.shell(f'am force-stop {package_name}')
        
    def release(self) -> None:
        """
        释放资源。
        """
        self.disconnect() 