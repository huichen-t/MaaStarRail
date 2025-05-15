"""
控制器模块。
负责设备连接、截图和控制的核心功能。
包括：
- 设备连接管理
- 截图功能
- 基础控制功能（点击、滑动等）
- 命令转发
"""

import os
import time
from typing import Optional, Tuple
import numpy as np
from PIL import Image

from module.device.device import Device
from module.base.logger import logger


class Controller:
    """
    设备控制器类。
    负责设备连接、截图和控制的核心功能。
    
    主要职责：
    1. 设备连接管理
       - 连接模拟器/设备
       - 管理连接状态
       - 处理连接异常
    
    2. 截图功能
       - 获取屏幕截图
       - 保存截图
       - 图像处理
    
    3. 基础控制功能
       - 点击操作
       - 滑动操作
       - 拖动操作
       - 按键操作
    
    4. 命令转发
       - 转发控制命令
       - 处理命令响应
       - 错误处理
    """
    
    def __init__(self, config=None, serial: Optional[str] = None):
        """
        初始化控制器。
        
        Args:
            config: 配置对象
            serial: 设备序列号，None表示自动检测
        """
        # 初始化设备连接
        self.device = Device(config=config, serial=serial)
        
        # 创建截图保存目录
        if not os.path.exists('screenshots'):
            os.makedirs('screenshots')
            
        # 初始化状态
        self._last_screenshot_time = 0
        self._screenshot_interval = 0.1  # 截图间隔时间（秒）
        
    def connect(self, serial: Optional[str] = None) -> bool:
        """
        连接设备。
        
        Args:
            serial: 设备序列号，None表示自动检测
            
        Returns:
            bool: 连接是否成功
        """
        try:
            if serial:
                self.device.adb_connect(serial)
            else:
                self.device.detect_device()
            return True
        except Exception as e:
            logger.error(f'设备连接失败: {str(e)}')
            return False
            
    def disconnect(self):
        """
        断开设备连接。
        """
        try:
            self.device.adb_disconnect()
        except Exception as e:
            logger.error(f'设备断开连接失败: {str(e)}')
            
    def screenshot(self, save: bool = False) -> np.ndarray:
        """
        获取屏幕截图。
        
        Args:
            save: 是否保存截图
            
        Returns:
            np.ndarray: 截图数据
        """
        # 控制截图频率
        current_time = time.time()
        if current_time - self._last_screenshot_time < self._screenshot_interval:
            time.sleep(self._screenshot_interval)
            
        try:
            # 获取截图
            self.device.screenshot()
            self._last_screenshot_time = time.time()
            
            # 保存截图
            if save:
                self._save_screenshot()
                
            return self.device.image
        except Exception as e:
            logger.error(f'截图失败: {str(e)}')
            return None
            
    def _save_screenshot(self):
        """
        保存当前截图。
        """
        try:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f'screenshots/screenshot_{timestamp}.png'
            Image.fromarray(self.device.image).save(filename)
            logger.info(f'截图已保存: {filename}')
        except Exception as e:
            logger.error(f'保存截图失败: {str(e)}')
            
    def click(self, x: int, y: int, duration: float = 0.1):
        """
        点击指定位置。
        
        Args:
            x: 横坐标
            y: 纵坐标
            duration: 点击持续时间
        """
        try:
            self.device.click((x, y), duration=duration)
        except Exception as e:
            logger.error(f'点击失败: {str(e)}')
            
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """
        滑动操作。
        
        Args:
            x1: 起始点横坐标
            y1: 起始点纵坐标
            x2: 结束点横坐标
            y2: 结束点纵坐标
            duration: 滑动持续时间
        """
        try:
            self.device.swipe((x1, y1), (x2, y2), duration=duration)
        except Exception as e:
            logger.error(f'滑动失败: {str(e)}')
            
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """
        拖动操作。
        
        Args:
            x1: 起始点横坐标
            y1: 起始点纵坐标
            x2: 结束点横坐标
            y2: 结束点纵坐标
            duration: 拖动持续时间
        """
        try:
            self.device.drag((x1, y1), (x2, y2), duration=duration)
        except Exception as e:
            logger.error(f'拖动失败: {str(e)}')
            
    def press_key(self, key: str):
        """
        按键操作。
        
        Args:
            key: 按键名称
        """
        try:
            self.device.press_key(key)
        except Exception as e:
            logger.error(f'按键失败: {str(e)}')
            
    def input_text(self, text: str):
        """
        输入文本。
        
        Args:
            text: 要输入的文本
        """
        try:
            self.device.input_text(text)
        except Exception as e:
            logger.error(f'输入文本失败: {str(e)}')
            
    def get_screen_size(self) -> Tuple[int, int]:
        """
        获取屏幕尺寸。
        
        Returns:
            Tuple[int, int]: (宽度, 高度)
        """
        try:
            return self.device.get_screen_size()
        except Exception as e:
            logger.error(f'获取屏幕尺寸失败: {str(e)}')
            return (0, 0)
            
    def is_connected(self) -> bool:
        """
        检查设备是否已连接。
        
        Returns:
            bool: 是否已连接
        """
        try:
            return self.device.is_connected()
        except Exception as e:
            logger.error(f'检查连接状态失败: {str(e)}')
            return False
            
    def get_device_info(self) -> dict:
        """
        获取设备信息。
        
        Returns:
            dict: 设备信息字典
        """
        try:
            return {
                'serial': self.device.serial,
                'screen_size': self.get_screen_size(),
                'is_connected': self.is_connected()
            }
        except Exception as e:
            logger.error(f'获取设备信息失败: {str(e)}')
            return {}
            
    def set_screenshot_interval(self, interval: float):
        """
        设置截图间隔时间。
        
        Args:
            interval: 间隔时间（秒）
        """
        self._screenshot_interval = max(0.01, interval)  # 最小间隔0.01秒
        
    def release(self):
        """
        释放资源。
        """
        try:
            self.device.release_resource()
        except Exception as e:
            logger.error(f'释放资源失败: {str(e)}')


# 使用示例
if __name__ == '__main__':
    # 创建控制器实例
    controller = Controller()
    
    # 连接设备
    if controller.connect():
        print('设备连接成功')
        
        # 获取设备信息
        info = controller.get_device_info()
        print(f'设备信息: {info}')
        
        # 获取截图
        image = controller.screenshot(save=True)
        if image is not None:
            print(f'截图尺寸: {image.shape}')
            
        # 执行点击操作
        controller.click(100, 100)
        
        # 执行滑动操作
        controller.swipe(100, 500, 100, 100)
        
        # 释放资源
        controller.release()
    else:
        print('设备连接失败')
