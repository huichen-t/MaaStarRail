"""
Nemu控制器模块。
提供通过Nemu IPC控制Nemu模拟器的功能。
Nemu是一个Android模拟器，通过IPC接口提供设备控制功能。
"""
import time
from typing import Tuple, Optional
import numpy as np
from adbutils.errors import AdbError

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


class NemuController(DeviceController):
    """
    Nemu控制器。
    提供通过Nemu IPC控制Nemu模拟器的功能。
    """
    
    def __init__(self, config):
        """
        初始化Nemu控制器。
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        self.nemu_ipc = None
        self.max_x = 0
        self.max_y = 0
        
    def connect(self) -> bool:
        """
        连接设备。
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 初始化Nemu IPC连接
            self.nemu_ipc_init()
            return True
        except Exception as e:
            logger.error(f'Failed to connect to device: {e}')
            return False
            
    def disconnect(self) -> None:
        """
        断开设备连接。
        """
        if self.nemu_ipc:
            self.nemu_ipc.close()
            self.nemu_ipc = None
            
    def nemu_ipc_init(self) -> None:
        """
        初始化Nemu IPC连接。
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
                
        # 启动Nemu IPC服务
        self.device.shell('pkill -f nemu_ipc')
        self.device.shell('nemu_ipc')
        
        # 建立连接
        self.nemu_ipc = self.device.shell('nemu_ipc', stream=True)
        
        # 等待服务启动
        time.sleep(0.5)
        
        # 发送初始化命令
        self.nemu_ipc.write(b'v 1\n')
        self.nemu_ipc.write(b'^ 1\n')
        self.nemu_ipc.write(b'$ 1\n')
        self.nemu_ipc.flush()
        
    @retry
    def click(self, x: int, y: int) -> None:
        """
        执行点击操作。
        
        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
        """
        # 发送点击命令
        self.nemu_ipc.write(f'click {x} {y}\n'.encode())
        self.nemu_ipc.flush()
        
    @retry
    def long_click(self, x: int, y: int, duration: float = 1.0) -> None:
        """
        执行长按操作。
        
        Args:
            x: 长按位置的x坐标
            y: 长按位置的y坐标
            duration: 长按持续时间（秒）
        """
        # 发送长按命令
        self.nemu_ipc.write(f'long_click {x} {y} {int(duration * 1000)}\n'.encode())
        self.nemu_ipc.flush()
        
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
        # 发送滑动命令
        self.nemu_ipc.write(f'swipe {x1} {y1} {x2} {y2} {int(duration * 1000)}\n'.encode())
        self.nemu_ipc.flush()
        
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
        # 发送拖拽命令
        self.nemu_ipc.write(f'drag {x1} {y1} {x2} {y2} {int(duration * 1000)}\n'.encode())
        self.nemu_ipc.flush()
        
    @retry
    def screenshot(self) -> np.ndarray:
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 屏幕截图数据
        """
        # 发送截图命令
        self.nemu_ipc.write(b'screenshot\n')
        self.nemu_ipc.flush()
        
        # 读取图片数据
        image_data = self.nemu_ipc.read()
        if not image_data:
            raise ImageTruncated('Empty image after reading from buffer')
            
        # 转换为numpy数组
        image = np.frombuffer(image_data, dtype=np.uint8)
        return image
        
    @retry
    def get_resolution(self) -> Tuple[int, int]:
        """
        获取设备分辨率。
        
        Returns:
            Tuple[int, int]: (宽度, 高度)
        """
        # 发送获取分辨率命令
        self.nemu_ipc.write(b'get_resolution\n')
        self.nemu_ipc.flush()
        
        # 读取分辨率数据
        resolution = self.nemu_ipc.readline().decode().strip()
        width, height = map(int, resolution.split('x'))
        return width, height
        
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
            # 发送启动应用命令
            self.nemu_ipc.write(f'app_start {package_name}\n'.encode())
            self.nemu_ipc.flush()
            
            # 读取响应
            response = self.nemu_ipc.readline().decode().strip()
            return response == 'success'
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
        # 发送停止应用命令
        self.nemu_ipc.write(f'app_stop {package_name}\n'.encode())
        self.nemu_ipc.flush()
        
    def release(self) -> None:
        """
        释放资源。
        """
        self.disconnect() 