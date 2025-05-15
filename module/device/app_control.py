from lxml import etree

from module.base.timer import Timer
from module.device.method.adb import Adb
from module.device.method.uiautomator_2 import Uiautomator2
from module.device.method.utils import HierarchyButton
from module.device.method.wsa import WSA
from module.exception import ScriptError
from module.base.logger import logger


class AppControl(Adb, WSA, Uiautomator2):
    """
    应用程序控制类，继承自Adb、WSA和Uiautomator2。
    用于管理Android应用程序的启动、停止和状态检测。
    """
    hierarchy: etree._Element
    # 使用ADB进行所有操作
    # 参见 https://github.com/openatx/uiautomator2/issues/565
    _app_u2_family = []
    _hierarchy_interval = Timer(0.1)

    def app_current(self) -> str:
        """
        获取当前运行的应用包名。
        根据不同的控制方法（WSA、uiautomator2或ADB）选择相应的实现。
        
        Returns:
            str: 当前运行的应用包名
        """
        method = self.config.Emulator_ControlMethod
        if self.is_wsa:
            package = self.app_current_wsa()
        elif method in AppControl._app_u2_family:
            package = self.app_current_uiautomator2()
        else:
            package = self.app_current_adb()
        package = package.strip(' \t\r\n')
        return package

    def app_is_running(self) -> bool:
        """
        检查目标应用是否正在运行。
        
        Returns:
            bool: 如果目标应用正在运行则返回True，否则返回False
        """
        package = self.app_current()
        logger.attr('Package_name', package)
        return package == self.package

    def app_start(self):
        """
        启动目标应用。
        根据不同的控制方法选择相应的启动实现。
        """
        method = self.config.Emulator_ControlMethod
        logger.info(f'App start: {self.package}')
        if self.config.Emulator_Serial == 'wsa-0':
            self.app_start_wsa(display=0)
        elif method in AppControl._app_u2_family:
            self.app_start_uiautomator2()
        else:
            self.app_start_adb()

    def app_stop(self):
        """
        停止目标应用。
        根据不同的控制方法选择相应的停止实现。
        """
        method = self.config.Emulator_ControlMethod
        logger.info(f'App stop: {self.package}')
        if method in AppControl._app_u2_family:
            self.app_stop_uiautomator2()
        else:
            self.app_stop_adb()

    def hierarchy_timer_set(self, interval=None):
        """
        设置界面层级获取的时间间隔。
        
        Args:
            interval (float, optional): 时间间隔（秒）。默认为0.1秒。
        
        Raises:
            ScriptError: 当interval参数类型无效时抛出
        """
        if interval is None:
            interval = 0.1
        elif isinstance(interval, (int, float)):
            # 代码中手动设置时没有限制
            pass
        else:
            logger.warning(f'Unknown hierarchy interval: {interval}')
            raise ScriptError(f'Unknown hierarchy interval: {interval}')

        if interval != self._hierarchy_interval.limit:
            logger.info(f'Hierarchy interval set to {interval}s')
            self._hierarchy_interval.limit = interval

    def dump_hierarchy(self) -> etree._Element:
        """
        获取当前界面的层级结构。
        使用uiautomator2获取界面层级信息。
        
        Returns:
            etree._Element: 界面层级树，可以使用xpath进行元素查找
                          例如：self.hierarchy.xpath('//*[@text="Hermit"]')
        """
        self._hierarchy_interval.wait()
        self._hierarchy_interval.reset()

        # 使用uiautomator2获取界面层级
        self.hierarchy = self.dump_hierarchy_uiautomator2()
        return self.hierarchy

    def xpath_to_button(self, xpath: str) -> HierarchyButton:
        """
        将xpath路径转换为可点击的按钮对象。
        
        Args:
            xpath (str): 要查找元素的xpath路径

        Returns:
            HierarchyButton: 具有类似Button对象方法和属性的按钮对象
                           如果未找到元素或找到多个元素则返回None
        """
        return HierarchyButton(self.hierarchy, xpath)
