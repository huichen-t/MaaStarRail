"""
minitouch控制器模块。
提供通过minitouch控制Android设备的功能。
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


class MinitouchController(DeviceController):
    """
    minitouch控制器。
    提供通过minitouch控制Android设备的功能。
    """
    
    def __init__(self, config):
        """
        初始化minitouch控制器。
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        self.minitouch = None
        self.max_x = 0
        self.max_y = 0
        
    def connect(self) -> bool:
        """
        连接设备。
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 初始化minitouch连接
            self.minitouch_init()
            return True
        except Exception as e:
            logger.error(f'Failed to connect to device: {e}')
            return False
            
    def disconnect(self) -> None:
        """
        断开设备连接。
        """
        if self.minitouch:
            self.minitouch.close()
            self.minitouch = None
            
    def minitouch_init(self) -> None:
        """
        初始化minitouch连接。
        设置屏幕参数并建立连接。
        """
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
                
        # 启动minitouch服务
        self.device.shell('pkill -f minitouch')
        self.device.shell('minitouch')
        
        # 建立连接
        self.minitouch = self.device.shell('minitouch', stream=True)
        
        # 等待服务启动
        time.sleep(0.5)
        
        # 发送初始化命令
        self.minitouch.write(b'v 1\n')
        self.minitouch.write(b'^ 1\n')
        self.minitouch.write(b'$ 1\n')
        self.minitouch.flush()
        
    @retry
    def click(self, x: int, y: int) -> None:
        """
        执行点击操作。
        
        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
        """
        # 发送按下命令
        self.minitouch.write(f'd 0 {x} {y} 50\n'.encode())
        self.minitouch.flush()
        time.sleep(0.05)
        
        # 发送抬起命令
        self.minitouch.write(b'u 0\n')
        self.minitouch.flush()
        
    @retry
    def long_click(self, x: int, y: int, duration: float = 1.0) -> None:
        """
        执行长按操作。
        
        Args:
            x: 长按位置的x坐标
            y: 长按位置的y坐标
            duration: 长按持续时间（秒）
        """
        # 发送按下命令
        self.minitouch.write(f'd 0 {x} {y} 50\n'.encode())
        self.minitouch.flush()
        
        # 等待指定时间
        time.sleep(duration)
        
        # 发送抬起命令
        self.minitouch.write(b'u 0\n')
        self.minitouch.flush()
        
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
        # 计算步长
        steps = int(duration * 50)  # 50Hz采样率
        if steps < 1:
            steps = 1
            
        # 计算每步的位移
        dx = (x2 - x1) / steps
        dy = (y2 - y1) / steps
        
        # 发送按下命令
        self.minitouch.write(f'd 0 {x1} {y1} 50\n'.encode())
        self.minitouch.flush()
        
        # 发送移动命令
        for i in range(1, steps + 1):
            x = int(x1 + dx * i)
            y = int(y1 + dy * i)
            self.minitouch.write(f'm 0 {x} {y} 50\n'.encode())
            self.minitouch.flush()
            time.sleep(duration / steps)
            
        # 发送抬起命令
        self.minitouch.write(b'u 0\n')
        self.minitouch.flush()
        
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
        # 拖拽操作与滑动操作类似
        self.swipe(x1, y1, x2, y2, duration)
        
    @retry
    def screenshot(self) -> np.ndarray:
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 屏幕截图数据
        """
        # 使用ADB截图
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
        # 使用minitouch的最大坐标作为分辨率
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