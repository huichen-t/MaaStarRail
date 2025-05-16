"""
截图管理器模块。
管理所有可用的截图方法，提供统一的截图接口。
"""

import os
import time
from collections import deque
from datetime import datetime
from typing import Dict, Optional

import cv2
import numpy as np
from PIL import Image

from module.base.decorator import cached_property
from module.base.timer import Timer
from module.base.utils import get_color, image_size, limit_in, save_image
from module.device.method.adb import Adb
from module.device.method.ascreencap import AScreenCap
from module.device.method.droidcast import DroidCast
from module.device.method.scrcpy import Scrcpy
from module.device.method.nemu_ipc import NemuIpc
from module.device.method.ldopengl import LDOpenGL
from module.device.screenshot.base import ScreenshotMethod
from module.device.screenshot.methods import (
    AdbScreenshot,
    AScreenCapScreenshot,
    DroidCastScreenshot,
    ScrcpyScreenshot,
    NemuIpcScreenshot,
    LDOpenGLScreenshot
)
from module.exception import RequestHumanTakeover, ScriptError
from module.base.logger import logger


class ScreenshotManager:
    """
    截图管理器类。
    管理所有可用的截图方法，提供统一的截图接口。
    
    Attributes:
        adb (Adb): ADB实例
        ascreencap (AScreenCap): aScreenCap实例
        droidcast (DroidCast): DroidCast实例
        scrcpy (Scrcpy): scrcpy实例
        nemu_ipc (NemuIpc): Nemu IPC实例
        ldopengl (LDOpenGL): LD OpenGL实例
        config: 配置对象
        _screen_size_checked (bool): 屏幕尺寸检查标志
        _screen_black_checked (bool): 屏幕黑屏检查标志
        _minicap_uninstalled (bool): minicap卸载标志
        _screenshot_interval (Timer): 截图间隔计时器
        _last_save_time (dict): 最后保存时间记录
        image (np.ndarray): 当前截图
    """
    
    def __init__(self, config, adb: Adb, ascreencap: AScreenCap, droidcast: DroidCast,
                 scrcpy: Scrcpy, nemu_ipc: NemuIpc, ldopengl: LDOpenGL):
        """
        初始化截图管理器。
        
        Args:
            config: 配置对象
            adb: ADB实例
            ascreencap: aScreenCap实例
            droidcast: DroidCast实例
            scrcpy: scrcpy实例
            nemu_ipc: Nemu IPC实例
            ldopengl: LD OpenGL实例
        """
        self.config = config
        self.adb = adb
        self.ascreencap = ascreencap
        self.droidcast = droidcast
        self.scrcpy = scrcpy
        self.nemu_ipc = nemu_ipc
        self.ldopengl = ldopengl
        
        self._screen_size_checked = False
        self._screen_black_checked = False
        self._minicap_uninstalled = False
        self._screenshot_interval = Timer(0.1)
        self._last_save_time = {}
        self.image = None
        
        # 初始化所有截图方法
        self._init_screenshot_methods()
    
    def _init_screenshot_methods(self):
        """初始化所有截图方法"""
        self._methods: Dict[str, ScreenshotMethod] = {
            'ADB': AdbScreenshot(self.adb),
            'aScreenCap': AScreenCapScreenshot(self.ascreencap),
            'DroidCast': DroidCastScreenshot(self.droidcast),
            'scrcpy': ScrcpyScreenshot(self.scrcpy),
            'nemu_ipc': NemuIpcScreenshot(self.nemu_ipc),
            'ldopengl': LDOpenGLScreenshot(self.ldopengl)
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
        available = self.nemu_ipc.nemu_ipc_available()
        logger.attr('nemu_ipc_available', available)
        if available:
            return 'nemu_ipc'
        # 检查ldopengl是否可用
        available = self.ldopengl.ldopengl_available()
        logger.attr('ldopengl_available', available)
        if available:
            return 'ldopengl'
        return ''
    
    def screenshot(self) -> np.ndarray:
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
            
            # 获取截图方法实例
            screenshot_method = self._methods.get(method)
            if screenshot_method is None:
                logger.warning(f'未知的截图方法: {method}，使用ADB方法')
                screenshot_method = self._methods['ADB']
            
            # 执行截图
            self.image = screenshot_method.screenshot()
            
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
    
    def _handle_orientated_image(self, image: np.ndarray) -> np.ndarray:
        """
        处理旋转的图像。
        将图像旋转到正确的方向。
        
        Args:
            image: 原始图像
            
        Returns:
            np.ndarray: 处理后的图像
        """
        width, height = image_size(image)
        if width == 1280 and height == 720:
            return image
        
        # 根据屏幕方向旋转图像
        if self.adb.orientation == 0:
            pass
        elif self.adb.orientation == 1:
            image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif self.adb.orientation == 2:
            image = cv2.rotate(image, cv2.ROTATE_180)
        elif self.adb.orientation == 3:
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        else:
            raise ScriptError(f'无效的设备方向: {self.adb.orientation}')
        
        return image
    
    @cached_property
    def screenshot_deque(self) -> deque:
        """
        获取截图队列。
        用于保存错误截图。
        
        Returns:
            deque: 截图队列
        """
        try:
            length = int(self.config.Error_ScreenshotLength)
        except ValueError:
            logger.error(f'Error_ScreenshotLength={self.config.Error_ScreenshotLength} 不是整数')
            raise RequestHumanTakeover
        # 限制队列长度在1~300之间
        length = max(1, min(length, 300))
        return deque(maxlen=length)
    
    def save_screenshot(self, genre='items', interval=None, to_base_folder=False) -> bool:
        """
        保存截图。
        使用毫秒时间戳作为文件名。
        
        Args:
            genre: 截图类型
            interval: 两次保存之间的间隔时间（秒）
            to_base_folder: 是否保存到基础文件夹
            
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
    
    def screenshot_last_save_time_reset(self, genre: str):
        """
        重置最后保存时间。
        
        Args:
            genre: 截图类型
        """
        self._last_save_time[genre] = 0
    
    def screenshot_interval_set(self, interval=None):
        """
        设置截图间隔。
        
        Args:
            interval: 两次截图之间的最小间隔时间（秒）
                或None使用Optimization_ScreenshotInterval
                或'combat'使用Optimization_CombatScreenshotInterval
        """
        if interval is None:
            # 设置普通截图间隔
            origin = self.config.Optimization_ScreenshotInterval
            interval = limit_in(origin, 0.1, 0.3)
            if interval != origin:
                logger.warning(f'Optimization.ScreenshotInterval {origin} 已修改为 {interval}')
                self.config.Optimization_ScreenshotInterval = interval
            # 允许nemu_ipc使用更低的默认值
            if self.config.Emulator_ScreenshotMethod == 'nemu_ipc':
                interval = limit_in(origin, 0.1, 0.2)
        elif interval == 'combat':
            # 设置战斗截图间隔
            origin = self.config.Optimization_CombatScreenshotInterval
            interval = limit_in(origin, 0.3, 1.0)
            if interval != origin:
                logger.warning(f'Optimization.CombatScreenshotInterval {origin} 已修改为 {interval}')
                self.config.Optimization_CombatScreenshotInterval = interval
        elif isinstance(interval, (int, float)):
            # 手动设置的间隔没有限制
            pass
        else:
            logger.warning(f'未知的截图间隔: {interval}')
            raise ScriptError(f'未知的截图间隔: {interval}')
        
        # scrcpy的截图间隔没有意义，因为视频流是持续接收的
        if not self.screenshot_method_override:
            if self.config.Emulator_ScreenshotMethod == 'scrcpy':
                interval = 0.1
        
        if interval != self._screenshot_interval.limit:
            logger.info(f'截图间隔设置为 {interval}s')
            self._screenshot_interval.limit = interval
    
    def image_show(self, image=None):
        """
        显示图像。
        
        Args:
            image: 要显示的图像，默认为当前截图
        """
        if image is None:
            image = self.image
        Image.fromarray(image).show()
    
    def image_save(self, file=None):
        """
        保存图像。
        
        Args:
            file: 保存路径，默认为时间戳.png
        """
        if file is None:
            file = f'{int(time.time() * 1000)}.png'
        save_image(self.image, file)
    
    def check_screen_size(self) -> bool:
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
                logger.info('收到旋转的截图，正在处理')
                self.adb.get_orientation()
                self.image = self._handle_orientated_image(self.image)
                orientated = True
                width, height = image_size(self.image)
                if width == 720 and height == 1280:
                    logger.info('无法处理旋转的截图，暂时继续')
                    return True
                else:
                    continue
            elif self.config.Emulator_Serial == 'wsa-0':
                # 处理WSA特殊情况
                self.adb.display_resize_wsa(0)
                return False
            elif hasattr(self.adb, 'app_is_running') and not self.adb.app_is_running():
                logger.warning('收到旋转的截图，游戏未运行')
                return True
            else:
                logger.critical(f'不支持的分辨率: {width}x{height}')
                logger.critical('请将模拟器分辨率设置为1280x720')
                raise RequestHumanTakeover
    
    def check_screen_black(self) -> bool:
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
                    display = self.adb.get_display_id()
                    if display == 0:
                        return True
                logger.info(f'游戏运行在显示器 {display} 上')
                logger.warning('游戏未在显示器0上运行，将重新启动')
                self.adb.app_stop_uiautomator2()
                return False
            elif self.config.Emulator_ScreenshotMethod == 'uiautomator2':
                # 处理uiautomator2特殊情况
                logger.warning(f'从模拟器收到纯黑截图，颜色: {color}')
                logger.warning('卸载minicap并重试')
                self.adb.uninstall_minicap()
                self._screen_black_checked = False
                return False
            else:
                # 处理其他模拟器
                if self.adb.is_mumu_family:
                    if self.config.Emulator_ScreenshotMethod == 'DroidCast':
                        self.droidcast.droidcast_stop()
                    else:
                        logger.warning('如果您使用的是MuMu X，请升级到版本 >= 12.1.5.0')
                self._screen_black_checked = False
                return False
        else:
            self._screen_black_checked = True
            return True 