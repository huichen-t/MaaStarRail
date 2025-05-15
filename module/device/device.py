"""
设备管理模块。
提供设备控制、截图、应用管理等功能的统一接口。
包括：
- 设备初始化和管理
- 截图方法管理
- 控制方法管理
- 应用管理
- 状态监控和错误处理
"""

import collections
import itertools

from lxml import etree

from module.device.env import IS_WINDOWS
# 在导入adbutils和uiautomator2之前修补pkg_resources
from module.device.pkg_resources import get_distribution
from module.test.benchmark import Benchmark

# 避免被导入优化移除
_ = get_distribution

from module.base.timer import Timer
from module.device.app_control import AppControl
from module.device.control import Control
from module.device.screenshot import Screenshot
from module.exception import (
    EmulatorNotRunningError,
    GameNotRunningError,
    GameStuckError,
    GameTooManyClickError,
    RequestHumanTakeover
)
from module.base.logger import logger




class Device(Screenshot, Control, AppControl):
    """
    设备管理类。
    继承自Screenshot、Control和AppControl，提供统一的设备管理接口。
    负责：
    - 设备初始化和管理
    - 截图方法管理
    - 控制方法管理
    - 应用管理
    - 状态监控和错误处理
    """
    _screen_size_checked = False  # 屏幕尺寸检查标志
    detect_record = set()  # 检测记录集合
    click_record = collections.deque(maxlen=30)  # 点击记录队列，最多记录30次
    stuck_timer = Timer(60, count=60).start()  # 卡住检测计时器

    def __init__(self, *args, **kwargs):
        """
        初始化设备。
        尝试连接设备，如果失败则重试最多3次。
        如果仍然失败，则请求人工干预。
        """
        for trial in range(4):
            try:
                super().__init__(*args, **kwargs)
                break
            except EmulatorNotRunningError:
                if trial >= 3:
                    logger.critical('Failed to start emulator after 3 trial')
                    raise RequestHumanTakeover
                # 尝试启动模拟器
                if self.emulator_instance is not None:
                    self.emulator_start()
                else:
                    logger.critical(
                        f'No emulator with serial "{self.config.Emulator_Serial}" found, '
                        f'please set a correct serial'
                    )
                    raise RequestHumanTakeover

        # 自动填充模拟器信息
        if IS_WINDOWS and self.config.EmulatorInfo_Emulator == 'auto':
            _ = self.emulator_instance

        self.screenshot_interval_set()
        self.method_check()

        # 自动选择最快的截图方法
        if not self.config.is_template_config and self.config.Emulator_ScreenshotMethod == 'auto':
            self.run_simple_screenshot_benchmark()

        # 早期初始化
        if self.config.is_actual_task:
            if self.config.Emulator_ControlMethod == 'MaaTouch':
                self.early_maatouch_init()
            if self.config.Emulator_ControlMethod == 'minitouch':
                self.early_minitouch_init()

    def run_simple_screenshot_benchmark(self):
        """
        执行截图方法基准测试。
        对每种方法测试3次，选择最快的方法。
        将最快的方法设置到config_src中。
        """
        logger.info('run_simple_screenshot_benchmark')
        # 首先检查分辨率
        self.resolution_check_uiautomator2()
        # 执行基准测试

        bench = Benchmark(config=self.config, device=self)
        method = bench.run_simple_screenshot_benchmark()
        # 设置
        with self.config.multi_set():
            self.config.Emulator_ScreenshotMethod = method

    def method_check(self):
        """
        检查截图方法和控制方法的组合。
        确保使用兼容的方法组合。
        """
        # 允许Hermit仅在VMOS上使用
        if self.config.Emulator_ControlMethod == 'Hermit' and not self.is_vmos:
            logger.warning('ControlMethod Hermit is allowed on VMOS only')
            self.config.Emulator_ControlMethod = 'MaaTouch'
        if self.config.Emulator_ScreenshotMethod == 'ldopengl' \
                and self.config.Emulator_ControlMethod == 'minitouch':
            logger.warning('Use MaaTouch on ldplayer')
            self.config.Emulator_ControlMethod = 'MaaTouch'

        # 如果在不支持的模拟器上选择了nemu_ipc或ldopengl，回退到auto
        if self.config.Emulator_ScreenshotMethod == 'nemu_ipc':
            if not (self.is_emulator and self.is_mumu_family):
                logger.warning('ScreenshotMethod nemu_ipc is available on MuMu Player 12 only, fallback to auto')
                self.config.Emulator_ScreenshotMethod = 'auto'
        if self.config.Emulator_ScreenshotMethod == 'ldopengl':
            if not (self.is_emulator and self.is_ldplayer_bluestacks_family):
                logger.warning('ScreenshotMethod ldopengl is available on LD Player only, fallback to auto')
                self.config.Emulator_ScreenshotMethod = 'auto'

    def screenshot(self):
        """
        获取屏幕截图。
        检查是否卡住，如果卡住则抛出异常。
        
        Returns:
            np.ndarray: 屏幕截图
        """
        self.stuck_record_check()

        try:
            super().screenshot()
        except RequestHumanTakeover:
            if not self.ascreencap_available:
                logger.error('aScreenCap unavailable on current device, fallback to auto')
                self.run_simple_screenshot_benchmark()
                super().screenshot()
            else:
                raise

        return self.image

    def dump_hierarchy(self) -> etree._Element:
        """
        获取界面层级结构。
        检查是否卡住，如果卡住则抛出异常。
        
        Returns:
            etree._Element: 界面层级结构
        """
        self.stuck_record_check()
        return super().dump_hierarchy()

    def release_during_wait(self):
        """
        在等待期间释放资源。
        停止scrcpy服务器和nemu_ipc。
        """
        # Scrcpy服务器仍在发送视频流，在等待期间停止它
        if self.config.Emulator_ScreenshotMethod == 'scrcpy':
            self._scrcpy_server_stop()
        if self.config.Emulator_ScreenshotMethod == 'nemu_ipc':
            self.nemu_ipc_release()

    def get_orientation(self):
        """
        获取屏幕方向。
        当方向改变时触发回调。
        
        Returns:
            int: 屏幕方向
        """
        o = super().get_orientation()

        self.on_orientation_change_maatouch()

        return o

    def stuck_record_add(self, button):
        """
        添加卡住检测记录。
        
        Args:
            button: 按钮对象
        """
        self.detect_record.add(str(button))

    def stuck_record_clear(self):
        """
        清除卡住检测记录。
        重置检测记录集合和计时器。
        """
        self.detect_record = set()
        self.stuck_timer.reset()

    def stuck_record_check(self):
        """
        检查是否卡住。
        如果等待时间过长，抛出GameStuckError异常。
        
        Raises:
            GameStuckError: 当等待时间过长时抛出
        """
        reached = self.stuck_timer.reached()
        if not reached:
            return False

        show_function_call()
        logger.warning('Wait too long')
        logger.warning(f'Waiting for {self.detect_record}')
        self.stuck_record_clear()

        if self.app_is_running():
            raise GameStuckError(f'Wait too long')
        else:
            raise GameNotRunningError('Game died')

    def handle_control_check(self, button):
        """
        处理控制检查。
        清除卡住记录，添加点击记录，检查点击记录。
        
        Args:
            button: 按钮对象
        """
        self.stuck_record_clear()
        self.click_record_add(button)
        self.click_record_check()

    def click_record_add(self, button):
        """
        添加点击记录。
        
        Args:
            button: 按钮对象
        """
        self.click_record.append(str(button))

    def click_record_clear(self):
        """
        清除点击记录。
        """
        self.click_record.clear()

    def click_record_remove(self, button):
        """
        从点击记录中移除按钮。
        
        Args:
            button (Button): 要移除的按钮
            
        Returns:
            int: 移除的按钮数量
        """
        removed = 0
        for _ in range(self.click_record.maxlen):
            try:
                self.click_record.remove(str(button))
                removed += 1
            except ValueError:
                # 值不在队列中
                break

        return removed

    def click_record_check(self):
        """
        检查点击记录。
        如果点击次数过多，抛出GameTooManyClickError异常。
        
        Raises:
            GameTooManyClickError: 当点击次数过多时抛出
        """
        first15 = itertools.islice(self.click_record, 0, 15)
        count = collections.Counter(first15).most_common(2)
        if count[0][1] >= 12:
            # 在阮梅事件中允许更多点击
            if 'CHOOSE_OPTION_CONFIRM' in self.click_record and 'BLESSING_CONFIRM' in self.click_record:
                count = collections.Counter(self.click_record).most_common(2)
                if count[0][0] == 'BLESSING_CONFIRM' and count[0][1] < 25:
                    return
            show_function_call()
            logger.warning(f'Too many click for a button: {count[0][0]}')
            logger.warning(f'History click: {[str(prev) for prev in self.click_record]}')
            self.click_record_clear()
            raise GameTooManyClickError(f'Too many click for a button: {count[0][0]}')
        if len(count) >= 2 and count[0][1] >= 6 and count[1][1] >= 6:
            show_function_call()
            logger.warning(f'Too many click between 2 buttons: {count[0][0]}, {count[1][0]}')
            logger.warning(f'History click: {[str(prev) for prev in self.click_record]}')
            self.click_record_clear()
            raise GameTooManyClickError(f'Too many click between 2 buttons: {count[0][0]}, {count[1][0]}')

    def disable_stuck_detection(self):
        """
        禁用卡住检测及其处理程序。
        通常用于半自动和调试。
        """
        logger.info('Disable stuck detection')

        def empty_function(*arg, **kwargs):
            return False

        self.click_record_check = empty_function
        self.stuck_record_check = empty_function

    def app_start(self):
        """
        启动应用。
        清除卡住记录和点击记录。
        """
        super().app_start()
        self.stuck_record_clear()
        self.click_record_clear()

    def app_stop(self):
        """
        停止应用。
        清除卡住记录和点击记录。
        """
        super().app_stop()
        self.stuck_record_clear()
        self.click_record_clear()
