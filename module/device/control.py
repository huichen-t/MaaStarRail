"""
游戏控制模块。
提供多种控制方法，支持不同模拟器和设备的点击、滑动等操作。
包括：
- ADB控制
- uiautomator2控制
- minitouch控制
- Hermit控制
- MaaTouch控制
- Nemu IPC控制
- scrcpy控制
"""
import numpy as np

from module.base.decorator import cached_property
from module.base.timer import Timer
from module.base.utils import *
from module.base.utils.str_utils import point2str
from module.device.controllers import (
    UiautomatorController,
    MinitouchController,
    HermitController,
    MaaTouchController,
    NemuController,
    ScrcpyController,
    AdbController
)
from module.logger import logger


class Control:
    """
    游戏控制类。
    使用组合模式整合多种控制方法，提供统一的控制接口。
    支持多种控制方式，自动选择最优方法。
    """
    def __init__(self, config):
        """
        初始化控制类。
        
        Args:
            config: 配置对象
        """
        self.config = config
        # 初始化各种控制方法
        self.controllers = {
            'uiautomator2': UiautomatorController(config),
            'minitouch': MinitouchController(config),
            'Hermit': HermitController(config),
            'MaaTouch': MaaTouchController(config),
            'nemu_ipc': NemuController(config),
            'scrcpy': ScrcpyController(config),
            'ADB': AdbController(config),
        }
        # 连接当前配置的控制方法
        self._connect_current_controller()

    def _connect_current_controller(self):
        """
        连接当前配置的控制方法。
        """
        method = self.config.Emulator_ControlMethod
        controller = self.controllers.get(method)
        if controller:
            if not controller.connect():
                logger.error(f'Failed to connect to {method} controller')
                raise RequestHumanTakeover

    def handle_control_check(self, button):
        """
        控制检查处理函数。
        将在Device类中被重写。
        
        Args:
            button: 按钮对象
        """
        # Will be overridden in Device
        pass

    @cached_property
    def click_methods(self):
        """
        获取所有可用的点击方法。
        
        Returns:
            dict: 点击方法字典，键为方法名，值为对应的方法函数
        """
        return {
            'ADB': self.controllers['ADB'].click,
            'uiautomator2': self.controllers['uiautomator2'].click,
            'minitouch': self.controllers['minitouch'].click,
            'Hermit': self.controllers['Hermit'].click,
            'MaaTouch': self.controllers['MaaTouch'].click,
            'nemu_ipc': self.controllers['nemu_ipc'].click,
        }

    def multi_click(self, button, n, interval=(0.1, 0.2)):
        """
        多次点击按钮。
        
        Args:
            button: 要点击的按钮
            n (int): 点击次数
            interval (tuple): 点击间隔时间范围（秒）
        """
        self.handle_control_check(button)
        click_timer = Timer(0.1)
        for _ in range(n):
            # 计算剩余等待时间
            remain = ensure_time(interval) - click_timer.current()
            if remain > 0:
                self.sleep(remain)
            click_timer.reset()

            self.click(button, control_check=False)

    def swipe(self, p1, p2, duration=(0.1, 0.2), name='SWIPE', distance_check=True):
        """
        滑动操作。
        
        Args:
            p1 (tuple): 起始点坐标
            p2 (tuple): 结束点坐标
            duration (tuple): 滑动持续时间范围（秒）
            name (str): 操作名称
            distance_check (bool): 是否检查滑动距离
        """
        self.handle_control_check(name)
        p1, p2 = ensure_int(p1, p2)
        duration = ensure_time(duration)
        method = self.config.Emulator_ControlMethod
        controller = self.controllers.get(method)
        
        # 根据不同控制方法记录日志
        if method == 'uiautomator2':
            logger.info('Swipe %s -> %s, %s' % (point2str(*p1), point2str(*p2), duration))
        elif method in ['minitouch', 'MaaTouch', 'scrcpy', 'nemu_ipc']:
            logger.info('Swipe %s -> %s' % (point2str(*p1), point2str(*p2)))
        else:
            # ADB需要较慢的速度，否则滑动可能无效
            duration *= 2.5
            logger.info('Swipe %s -> %s, %s' % (point2str(*p1), point2str(*p2), duration))

        # 检查滑动距离
        if distance_check:
            if np.linalg.norm(np.subtract(p1, p2)) < 10:
                # 滑动距离需要达到一定值，否则游戏会将其视为点击
                # uiautomator2需要>=6像素，minitouch需要>=5像素
                logger.info('Swipe distance < 10px, dropped')
                return

        # 执行滑动操作
        controller.swipe(p1[0], p1[1], p2[0], p2[1], duration=duration)

    def drag(self, p1, p2, segments=1, shake=(0, 15), point_random=(-10, -10, 10, 10), shake_random=(-5, -5, 5, 5),
             swipe_duration=0.25, shake_duration=0.1, name='DRAG'):
        """
        拖拽操作。
        
        Args:
            p1 (tuple): 起始点坐标
            p2 (tuple): 结束点坐标
            segments (int): 分段数
            shake (tuple): 抖动范围
            point_random (tuple): 点随机范围
            shake_random (tuple): 抖动随机范围
            swipe_duration (float): 滑动持续时间
            shake_duration (float): 抖动持续时间
            name (str): 操作名称
        """
        self.handle_control_check(name)
        p1, p2 = ensure_int(p1, p2)
        logger.info(
            'Drag %s -> %s' % (point2str(*p1), point2str(*p2))
        )
        # 根据控制方法选择对应的拖拽实现
        method = self.config.Emulator_ControlMethod
        controller = self.controllers.get(method)
        
        if method in ['minitouch', 'scrcpy', 'MaaTouch', 'nemu_ipc']:
            controller.drag(p1[0], p1[1], p2[0], p2[1], duration=swipe_duration)
        elif method == 'uiautomator2':
            controller.drag(p1[0], p1[1], p2[0], p2[1], duration=swipe_duration)
        else:
            # 对于不支持拖拽的控制方法，回退到ADB滑动
            logger.warning(f'Control method {method} does not support drag well, '
                           f'falling back to ADB swipe may cause unexpected behaviour')
            self.controllers['ADB'].swipe(p1[0], p1[1], p2[0], p2[1], duration=swipe_duration * 2)

    def release(self):
        """
        释放资源。
        释放所有控制方法的资源。
        """
        for controller in self.controllers.values():
            controller.release()

