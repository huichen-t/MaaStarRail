"""
游戏截图管理模块。
提供多种截图方法，支持不同模拟器和设备的截图功能。
包括：
- ADB截图
- uiautomator2截图
- aScreenCap截图
- DroidCast截图
- scrcpy截图
- Nemu IPC截图
- LD OpenGL截图
"""

import os
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np
from PIL import Image

from module.base.decorator import cached_property
from module.base.timer import Timer
from module.base.utils import get_color, image_size, limit_in, save_image
from module.device.method.adb import Adb
from module.device.method.ascreencap import AScreenCap
from module.device.method.droidcast import DroidCast
from module.device.method.ldopengl import LDOpenGL
from module.device.method.nemu_ipc import NemuIpc
from module.device.method.scrcpy import Scrcpy
from module.device.method.wsa import WSA
from module.exception import RequestHumanTakeover, ScriptError
from module.logger import logger


class Screenshot(Adb, WSA, DroidCast, AScreenCap, Scrcpy, NemuIpc, LDOpenGL):
    """
    截图管理类。
    继承自多种截图方法类，提供统一的截图接口。
    支持多种截图方式，自动选择最优方法。
    """
    # 屏幕尺寸检查标志
    _screen_size_checked = False
    # 屏幕黑屏检查标志
    _screen_black_checked = False
    # minicap卸载标志
    _minicap_uninstalled = False
    # 截图间隔计时器
    _screenshot_interval = Timer(0.1)
    # 最后保存时间记录
    _last_save_time = {}
    # 当前截图
    image: np.ndarray

    @cached_property
    def screenshot_methods(self):
        """
        获取所有可用的截图方法。
        
        Returns:
            dict: 截图方法字典，键为方法名，值为对应的方法函数
        """
        return {
            'ADB': self.screenshot_adb,
            'ADB_nc': self.screenshot_adb_nc,
            'uiautomator2': self.screenshot_uiautomator2,
            'aScreenCap': self.screenshot_ascreencap,
            'aScreenCap_nc': self.screenshot_ascreencap_nc,
            'DroidCast': self.screenshot_droidcast,
            'DroidCast_raw': self.screenshot_droidcast_raw,
            'scrcpy': self.screenshot_scrcpy,
            'nemu_ipc': self.screenshot_nemu_ipc,
            'ldopengl': self.screenshot_ldopengl,
        }

    @cached_property
    def screenshot_method_override(self) -> str:
        """
        获取覆盖的截图方法。
        优先使用nemu_ipc或ldopengl方法。
        
        Returns:
            str: 截图方法名称
        """
        # 检查nemu_ipc是否可用
        available = self.nemu_ipc_available()
        logger.attr('nemu_ipc_available', available)
        if available:
            return 'nemu_ipc'
        # 检查ldopengl是否可用
        available = self.ldopengl_available()
        logger.attr('ldopengl_available', available)
        if available:
            return 'ldopengl'
        return ''

    def screenshot(self):
        """
        获取屏幕截图。
        支持多种截图方法，自动选择最优方法。
        处理屏幕旋转和黑屏情况。
        
        Returns:
            np.ndarray: 截图图像数据
        """
        self._screenshot_interval.wait()
        self._screenshot_interval.reset()

        for _ in range(2):
            # 选择截图方法
            if self.screenshot_method_override:
                method = self.screenshot_method_override
            else:
                method = self.config.Emulator_ScreenshotMethod
            method = self.screenshot_methods.get(method, self.screenshot_adb)

            # 执行截图
            self.image = method()

            # 处理屏幕旋转
            self.image = self._handle_orientated_image(self.image)

            # 保存错误截图
            if self.config.Error_SaveError:
                self.screenshot_deque.append({'time': datetime.now(), 'image': self.image})

            # 检查屏幕尺寸和黑屏
            if self.check_screen_size() and self.check_screen_black():
                break
            else:
                continue

        return self.image

    @property
    def has_cached_image(self):
        """
        检查是否有缓存的图像。
        
        Returns:
            bool: 是否有缓存的图像
        """
        return hasattr(self, 'image') and self.image is not None

    def _handle_orientated_image(self, image):
        """
        处理旋转的图像。
        将图像旋转到正确的方向。
        
        Args:
            image (np.ndarray): 原始图像
            
        Returns:
            np.ndarray: 处理后的图像
        """
        width, height = image_size(self.image)
        if width == 1280 and height == 720:
            return image

        # 根据屏幕方向旋转图像
        if self.orientation == 0:
            pass
        elif self.orientation == 1:
            image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif self.orientation == 2:
            image = cv2.rotate(image, cv2.ROTATE_180)
        elif self.orientation == 3:
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        else:
            raise ScriptError(f'Invalid device orientation: {self.orientation}')

        return image

    @cached_property
    def screenshot_deque(self):
        """
        获取截图队列。
        用于保存错误截图。
        
        Returns:
            deque: 截图队列
        """
        try:
            length = int(self.config.Error_ScreenshotLength)
        except ValueError:
            logger.error(f'Error_ScreenshotLength={self.config.Error_ScreenshotLength} is not an integer')
            raise RequestHumanTakeover
        # 限制队列长度在1~300之间
        length = max(1, min(length, 300))
        return deque(maxlen=length)

    @cached_property
    def screenshot_tracking(self):
        """
        获取截图跟踪列表。
        
        Returns:
            list: 截图跟踪列表
        """
        return []

    def save_screenshot(self, genre='items', interval=None, to_base_folder=False):
        """
        保存截图。
        使用毫秒时间戳作为文件名。
        
        Args:
            genre (str): 截图类型
            interval (int, float): 两次保存之间的间隔时间（秒）
            to_base_folder (bool): 是否保存到基础文件夹
            
        Returns:
            bool: 是否保存成功
        """
        now = time.time()
        if interval is None:
            interval = self.config.SCREEN_SHOT_SAVE_INTERVAL

        if now - self._last_save_time.get(genre, 0) > interval:
            fmt = 'png'
            file = '%s.%s' % (int(now * 1000), fmt)

            # 选择保存文件夹
            folder = self.config.SCREEN_SHOT_SAVE_FOLDER_BASE if to_base_folder else self.config.SCREEN_SHOT_SAVE_FOLDER
            folder = os.path.join(folder, genre)
            if not os.path.exists(folder):
                os.mkdir(folder)

            file = os.path.join(folder, file)
            self.image_save(file)
            self._last_save_time[genre] = now
            return True
        else:
            self._last_save_time[genre] = now
            return False

    def screenshot_last_save_time_reset(self, genre):
        """
        重置最后保存时间。
        
        Args:
            genre (str): 截图类型
        """
        self._last_save_time[genre] = 0

    def screenshot_interval_set(self, interval=None):
        """
        设置截图间隔。
        
        Args:
            interval (int, float, str):
                两次截图之间的最小间隔时间（秒）
                或None使用Optimization_ScreenshotInterval
                或'combat'使用Optimization_CombatScreenshotInterval
        """
        if interval is None:
            # 设置普通截图间隔
            origin = self.config.Optimization_ScreenshotInterval
            interval = limit_in(origin, 0.1, 0.3)
            if interval != origin:
                logger.warning(f'Optimization.ScreenshotInterval {origin} is revised to {interval}')
                self.config.Optimization_ScreenshotInterval = interval
            # 允许nemu_ipc使用更低的默认值
            if self.config.Emulator_ScreenshotMethod == 'nemu_ipc':
                interval = limit_in(origin, 0.1, 0.2)
        elif interval == 'combat':
            # 设置战斗截图间隔
            origin = self.config.Optimization_CombatScreenshotInterval
            interval = limit_in(origin, 0.3, 1.0)
            if interval != origin:
                logger.warning(f'Optimization.CombatScreenshotInterval {origin} is revised to {interval}')
                self.config.Optimization_CombatScreenshotInterval = interval
        elif isinstance(interval, (int, float)):
            # 手动设置的间隔没有限制
            pass
        else:
            logger.warning(f'Unknown screenshot interval: {interval}')
            raise ScriptError(f'Unknown screenshot interval: {interval}')
            
        # scrcpy的截图间隔没有意义，因为视频流是持续接收的
        if not self.screenshot_method_override:
            if self.config.Emulator_ScreenshotMethod == 'scrcpy':
                interval = 0.1

        if interval != self._screenshot_interval.limit:
            logger.info(f'Screenshot interval set to {interval}s')
            self._screenshot_interval.limit = interval

    def image_show(self, image=None):
        """
        显示图像。
        
        Args:
            image (np.ndarray): 要显示的图像，默认为当前截图
        """
        if image is None:
            image = self.image
        Image.fromarray(image).show()

    def image_save(self, file=None):
        """
        保存图像。
        
        Args:
            file (str): 保存路径，默认为时间戳.png
        """
        if file is None:
            file = f'{int(time.time() * 1000)}.png'
        save_image(self.image, file)

    def check_screen_size(self):
        """
        检查屏幕尺寸。
        屏幕尺寸必须是1280x720。
        在调用此方法前必须先截图。
        
        Returns:
            bool: 屏幕尺寸是否正确
        """
        if self._screen_size_checked:
            return True

        orientated = False
        for _ in range(2):
            # 检查屏幕尺寸
            width, height = image_size(self.image)
            logger.attr('Screen_size', f'{width}x{height}')
            if width == 1280 and height == 720:
                self._screen_size_checked = True
                return True
            elif not orientated and (width == 720 and height == 1280):
                # 处理旋转的截图
                logger.info('Received orientated screenshot, handling')
                self.get_orientation()
                self.image = self._handle_orientated_image(self.image)
                orientated = True
                width, height = image_size(self.image)
                if width == 720 and height == 1280:
                    logger.info('Unable to handle orientated screenshot, continue for now')
                    return True
                else:
                    continue
            elif self.config.Emulator_Serial == 'wsa-0':
                # 处理WSA特殊情况
                self.display_resize_wsa(0)
                return False
            elif hasattr(self, 'app_is_running') and not self.app_is_running():
                logger.warning('Received orientated screenshot, game not running')
                return True
            else:
                logger.critical(f'Resolution not supported: {width}x{height}')
                logger.critical('Please set emulator resolution to 1280x720')
                raise RequestHumanTakeover

    def check_screen_black(self):
        """
        检查屏幕是否黑屏。
        
        Returns:
            bool: 屏幕是否正常
        """
        if self._screen_black_checked:
            return True
        # 检查屏幕颜色
        # 某些模拟器可能会获取到纯黑截图
        color = get_color(self.image, area=(0, 0, 1280, 720))
        if sum(color) < 1:
            if self.config.Emulator_Serial == 'wsa-0':
                # 处理WSA特殊情况
                for _ in range(2):
                    display = self.get_display_id()
                    if display == 0:
                        return True
                logger.info(f'Game running on display {display}')
                logger.warning('Game not running on display 0, will be restarted')
                self.app_stop_uiautomator2()
                return False
            elif self.config.Emulator_ScreenshotMethod == 'uiautomator2':
                # 处理uiautomator2特殊情况
                logger.warning(f'Received pure black screenshots from emulator, color: {color}')
                logger.warning('Uninstall minicap and retry')
                self.uninstall_minicap()
                self._screen_black_checked = False
                return False
            else:
                # 处理其他模拟器
                if self.is_mumu_family:
                    if self.config.Emulator_ScreenshotMethod == 'DroidCast':
                        self.droidcast_stop()
                    else:
                        logger.warning('If you are using MuMu X, please upgrade to version >= 12.1.5.0')
                self._screen_black_checked = False
                return False
        else:
            self._screen_black_checked = True
            return True
