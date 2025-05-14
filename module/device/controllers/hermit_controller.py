"""
Hermit控制器模块。
提供通过Hermit控制VMOS设备的功能。
Hermit是一个用于VMOS环境的控制工具，通过HTTP API提供设备控制功能。
"""
import time
from typing import Tuple, Optional
import requests
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


class HermitController(DeviceController):
    """
    Hermit控制器。
    提供通过Hermit控制VMOS设备的功能。
    """
    
    def __init__(self, config):
        """
        初始化Hermit控制器。
        
        Args:
            config: 配置对象
        """
        super().__init__(config)
        self.base_url = 'http://localhost:9999'
        self.session = requests.Session()
        
    def connect(self) -> bool:
        """
        连接设备。
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 检查Hermit服务是否可用
            response = self.session.get(f'{self.base_url}/ping')
            if response.status_code == 200:
                logger.info('Hermit service is available')
                return True
            else:
                logger.error(f'Hermit service returned status code: {response.status_code}')
                return False
        except Exception as e:
            logger.error(f'Failed to connect to Hermit service: {e}')
            return False
            
    def disconnect(self) -> None:
        """
        断开设备连接。
        """
        self.session.close()
        
    @retry
    def click(self, x: int, y: int) -> None:
        """
        执行点击操作。
        
        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
        """
        response = self.session.post(f'{self.base_url}/click', json={'x': x, 'y': y})
        if response.status_code != 200:
            raise RuntimeError(f'Click failed with status code: {response.status_code}')
            
    @retry
    def long_click(self, x: int, y: int, duration: float = 1.0) -> None:
        """
        执行长按操作。
        
        Args:
            x: 长按位置的x坐标
            y: 长按位置的y坐标
            duration: 长按持续时间（秒）
        """
        response = self.session.post(
            f'{self.base_url}/long_click',
            json={'x': x, 'y': y, 'duration': int(duration * 1000)}
        )
        if response.status_code != 200:
            raise RuntimeError(f'Long click failed with status code: {response.status_code}')
            
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
        response = self.session.post(
            f'{self.base_url}/swipe',
            json={
                'x1': x1, 'y1': y1,
                'x2': x2, 'y2': y2,
                'duration': int(duration * 1000)
            }
        )
        if response.status_code != 200:
            raise RuntimeError(f'Swipe failed with status code: {response.status_code}')
            
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
        # Hermit的拖拽操作与滑动操作类似
        self.swipe(x1, y1, x2, y2, duration)
        
    @retry
    def screenshot(self) -> np.ndarray:
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 屏幕截图数据
        """
        response = self.session.get(f'{self.base_url}/screenshot')
        if response.status_code != 200:
            raise RuntimeError(f'Screenshot failed with status code: {response.status_code}')
            
        # 将图片数据转换为numpy数组
        image = np.frombuffer(response.content, dtype=np.uint8)
        if image is None or len(image) == 0:
            raise ImageTruncated('Empty image after reading from buffer')
            
        return image
        
    @retry
    def get_resolution(self) -> Tuple[int, int]:
        """
        获取设备分辨率。
        
        Returns:
            Tuple[int, int]: (宽度, 高度)
        """
        response = self.session.get(f'{self.base_url}/resolution')
        if response.status_code != 200:
            raise RuntimeError(f'Get resolution failed with status code: {response.status_code}')
            
        data = response.json()
        return data['width'], data['height']
        
    @retry
    def app_start(self, package_name: str) -> bool:
        """
        启动应用。
        
        Args:
            package_name: 应用包名
            
        Returns:
            bool: 是否成功启动
        """
        response = self.session.post(
            f'{self.base_url}/app/start',
            json={'package_name': package_name}
        )
        if response.status_code != 200:
            logger.error(f'Failed to start app {package_name}: {response.text}')
            return False
        return True
        
    @retry
    def app_stop(self, package_name: str) -> None:
        """
        停止应用。
        
        Args:
            package_name: 应用包名
        """
        response = self.session.post(
            f'{self.base_url}/app/stop',
            json={'package_name': package_name}
        )
        if response.status_code != 200:
            raise RuntimeError(f'Stop app failed with status code: {response.status_code}')
            
    def release(self) -> None:
        """
        释放资源。
        """
        self.disconnect() 