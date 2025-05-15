"""
ADB控制模块。
提供通过ADB（Android Debug Bridge）控制Android设备的基础功能。
包括：
- 截图功能
- 点击和滑动操作
- 应用管理（启动/停止）
- 界面层级获取
- 错误处理和重试机制
"""

import re
import time
from functools import wraps

import cv2
import numpy as np
from adbutils.errors import AdbError
from lxml import etree

from module.base.decorator import Config
from module.config_src.server import DICT_PACKAGE_TO_ACTIVITY
from module.device.connection import Connection
from module.device.method.utils import (ImageTruncated, PackageNotInstalled, RETRY_TRIES, handle_adb_error,
                                        handle_unknown_host_service, remove_prefix, retry_sleep)
from module.exception import RequestHumanTakeover, ScriptError
from module.base.logger import logger


def retry(func):
    """
    重试装饰器。
    当函数执行失败时自动重试，最多重试RETRY_TRIES次。
    处理各种异常情况：
    - ADB连接重置
    - ADB错误
    - 包未安装
    - 图像截取错误
    - 其他未知错误
    
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
            # 无法处理的错误
            except RequestHumanTakeover:
                break
            # ADB服务器被杀死
            except ConnectionResetError as e:
                logger.error(e)

                def init():
                    self.adb_reconnect()
            # ADB错误
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
            # 包未安装
            except PackageNotInstalled as e:
                logger.error(e)

                def init():
                    self.detect_package()
            # 图像截取错误
            except ImageTruncated as e:
                logger.error(e)

                def init():
                    pass
            # 未知错误
            except Exception as e:
                logger.exception(e)

                def init():
                    pass

        logger.critical(f'Retry {func.__name__}() failed')
        raise RequestHumanTakeover

    return retry_wrapper


def load_screencap(data):
    """
    加载ADB screencap命令返回的原始数据。
    
    Args:
        data: screencap命令返回的原始数据
        
    Returns:
        np.ndarray: 解码后的图像数据
        
    Raises:
        ImageTruncated: 当图像数据无效时抛出
    """
    # 加载数据
    header = np.frombuffer(data[0:12], dtype=np.uint32)
    channel = 4  # screencap发送RGBA图像
    width, height, _ = header  # 通常是1280, 720, 1

    image = np.frombuffer(data, dtype=np.uint8)
    if image is None:
        raise ImageTruncated('Empty image after reading from buffer')

    try:
        image = image[-int(width * height * channel):].reshape(height, width, channel)
    except ValueError as e:
        # ValueError: cannot reshape array of size 0 into shape (720,1280,4)
        raise ImageTruncated(str(e))

    image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    if image is None:
        raise ImageTruncated('Empty image after cv2.cvtColor')

    return image


class Adb(Connection):
    """
    ADB控制类。
    提供通过ADB控制Android设备的各种功能。
    继承自Connection类，实现设备连接的基础功能。
    """
    __screenshot_method = [0, 1, 2]  # 截图方法列表
    __screenshot_method_fixed = [0, 1, 2]  # 固定的截图方法列表

    @staticmethod
    def __load_screenshot(screenshot, method):
        """
        加载截图数据。
        支持多种解码方法，处理不同设备返回的数据格式。
        
        Args:
            screenshot: 原始截图数据
            method: 解码方法（0,1,2）
            
        Returns:
            np.ndarray: 解码后的图像数据
            
        Raises:
            ScriptError: 当解码方法无效时抛出
            ImageTruncated: 当图像数据无效时抛出
        """
        if method == 0:
            pass
        elif method == 1:
            screenshot = screenshot.replace(b'\r\n', b'\n')
        elif method == 2:
            screenshot = screenshot.replace(b'\r\r\n', b'\n')
        else:
            raise ScriptError(f'Unknown method to load screenshots: {method}')

        # 修复VMOS Pro的兼容性问题
        # VMOS Pro的screencap输出会有一个额外的头部，需要移除
        screenshot = remove_prefix(screenshot, b'long long=8 fun*=10\n')

        image = np.frombuffer(screenshot, np.uint8)
        if image is None:
            raise ImageTruncated('Empty image after reading from buffer')

        image = cv2.imdecode(image, cv2.IMREAD_COLOR)
        if image is None:
            raise ImageTruncated('Empty image after cv2.imdecode')

        cv2.cvtColor(image, cv2.COLOR_BGR2RGB, dst=image)
        if image is None:
            raise ImageTruncated('Empty image after cv2.cvtColor')

        return image

    def __process_screenshot(self, screenshot):
        """
        处理截图数据。
        尝试不同的解码方法，直到成功或全部失败。
        
        Args:
            screenshot: 原始截图数据
            
        Returns:
            np.ndarray: 解码后的图像数据
            
        Raises:
            OSError: 当所有解码方法都失败时抛出
        """
        for method in self.__screenshot_method_fixed:
            try:
                result = self.__load_screenshot(screenshot, method=method)
                self.__screenshot_method_fixed = [method] + self.__screenshot_method
                return result
            except (OSError, ImageTruncated):
                continue

        self.__screenshot_method_fixed = self.__screenshot_method
        if len(screenshot) < 500:
            logger.warning(f'Unexpected screenshot: {screenshot}')
        raise OSError(f'cannot load screenshot')

    @retry
    @Config.when(DEVICE_OVER_HTTP=False)
    def screenshot_adb(self):
        """
        通过ADB获取屏幕截图（非HTTP模式）。
        
        Returns:
            np.ndarray: 屏幕截图数据
        """
        data = self.adb_shell(['screencap', '-p'], stream=True)
        if len(data) < 500:
            logger.warning(f'Unexpected screenshot: {data}')

        return self.__process_screenshot(data)

    @retry
    @Config.when(DEVICE_OVER_HTTP=True)
    def screenshot_adb(self):
        """
        通过ADB获取屏幕截图（HTTP模式）。
        
        Returns:
            np.ndarray: 屏幕截图数据
        """
        data = self.adb_shell(['screencap'], stream=True)
        if len(data) < 500:
            logger.warning(f'Unexpected screenshot: {data}')

        return load_screencap(data)

    @retry
    def screenshot_adb_nc(self):
        """
        通过ADB netcat获取屏幕截图。
        
        Returns:
            np.ndarray: 屏幕截图数据
        """
        data = self.adb_shell_nc(['screencap'])
        if len(data) < 500:
            logger.warning(f'Unexpected screenshot: {data}')

        return load_screencap(data)

    @retry
    def click_adb(self, x, y):
        """
        通过ADB执行点击操作。
        
        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
        """
        start = time.time()
        self.adb_shell(['input', 'tap', x, y])
        if time.time() - start <= 0.05:
            self.sleep(0.05)

    @retry
    def swipe_adb(self, p1, p2, duration=0.1):
        """
        通过ADB执行滑动操作。
        
        Args:
            p1: 起始点坐标
            p2: 结束点坐标
            duration: 滑动持续时间（秒）
        """
        duration = int(duration * 1000)
        self.adb_shell(['input', 'swipe', *p1, *p2, duration])

    @retry
    def app_current_adb(self):
        """
        获取当前运行的应用包名。
        从uiautomator2复制而来。
        
        Returns:
            str: 当前运行的应用包名
            
        Raises:
            OSError: 当无法获取当前应用时抛出
        """
        # 相关issue: https://github.com/openatx/uiautomator2/issues/200
        _focusedRE = re.compile(
            r'mCurrentFocus=Window{.*\s+(?P<package>[^\s]+)/(?P<activity>[^\s]+)\}'
        )
        m = _focusedRE.search(self.adb_shell(['dumpsys', 'window', 'windows']))
        if m:
            return m.group('package')

        # 尝试: adb shell dumpsys activity top
        _activityRE = re.compile(
            r'ACTIVITY (?P<package>[^\s]+)/(?P<activity>[^/\s]+) \w+ pid=(?P<pid>\d+)'
        )
        output = self.adb_shell(['dumpsys', 'activity', 'top'])
        ms = _activityRE.finditer(output)
        ret = None
        for m in ms:
            ret = m.group('package')
        if ret:  # 获取最后一个结果
            return ret
        raise OSError("Couldn't get focused app")

    @retry
    def _app_start_adb_monkey(self, package_name=None, allow_failure=False):
        """
        通过monkey命令启动应用。
        
        Args:
            package_name: 要启动的应用包名
            allow_failure: 是否允许启动失败
            
        Returns:
            bool: 是否成功启动
            
        Raises:
            PackageNotInstalled: 当应用未安装时抛出
        """
        if not package_name:
            package_name = self.package
        result = self.adb_shell([
            'monkey', '-p', package_name, '-c',
            'android.intent.category.LAUNCHER', '--pct-syskeys', '0', '1'
        ])
        if 'No activities found' in result:
            # ** No activities found to run, monkey aborted.
            if allow_failure:
                return False
            else:
                logger.error(result)
                raise PackageNotInstalled(package_name)
        elif 'inaccessible' in result:
            # /system/bin/sh: monkey: inaccessible or not found
            return False
        else:
            # Events injected: 1
            # ## Network stats: elapsed time=4ms (0ms mobile, 0ms wifi, 4ms not connected)
            return True

    @retry
    def _app_start_adb_am(self, package_name=None, activity_name=None, allow_failure=False):
        """
        通过am命令启动应用。
        
        Args:
            package_name: 要启动的应用包名
            activity_name: 要启动的Activity名称
            allow_failure: 是否允许启动失败
            
        Returns:
            bool: 是否成功启动
            
        Raises:
            PackageNotInstalled: 当应用未安装时抛出
        """
        if not package_name:
            package_name = self.package
        if not activity_name:
            result = self.adb_shell(['dumpsys', 'package', package_name])
            res = re.search(r'android.intent.action.MAIN:\s+\w+ ([\w.\/]+) filter \w+\s+'
                            r'.*\s+Category: "android.intent.category.LAUNCHER"',
                            result)
            if res:
                # com.bilibili.azurlane/com.manjuu.azurlane.MainActivity
                activity_name = res.group(1)
                try:
                    activity_name = activity_name.split('/')[-1]
                except IndexError:
                    logger.error(f'No activity name from {activity_name}')
                    return False
            else:
                if allow_failure:
                    return False
                else:
                    logger.error(result)
                    raise PackageNotInstalled(package_name)

        cmd = ['am', 'start', '-a', 'android.intent.action.MAIN', '-c',
               'android.intent.category.LAUNCHER', '-n', f'{package_name}/{activity_name}']
        if self.is_local_network_device and self.is_waydroid:
            cmd += ['--windowingMode', '4']
        ret = self.adb_shell(cmd)
        
        # 处理各种错误情况
        if 'Error: Activity class' in ret:
            if allow_failure:
                return False
            else:
                logger.error(ret)
                return False
        if 'Warning: Activity not started' in ret:
            logger.info('App activity is already started')
            return True
        if 'Permission Denial' in ret:
            if allow_failure:
                return False
            else:
                logger.error(ret)
                logger.error('Permission Denial while starting app, probably because activity invalid')
                return False
        return True

    def app_start_adb(self, package_name=None, activity_name=None, allow_failure=False):
        """
        启动应用。
        尝试多种方法启动应用：
        1. 使用am命令启动指定Activity
        2. 使用monkey命令启动
        3. 再次尝试使用am命令启动
        
        Args:
            package_name: 要启动的应用包名
            activity_name: 要启动的Activity名称
            allow_failure: 是否允许启动失败
            
        Returns:
            bool: 是否成功启动
            
        Raises:
            PackageNotInstalled: 当应用未安装时抛出
        """
        if not package_name:
            package_name = self.package
        if not activity_name:
            activity_name = DICT_PACKAGE_TO_ACTIVITY.get(package_name)

        if activity_name:
            if self._app_start_adb_am(package_name, activity_name, allow_failure):
                return True
        if self._app_start_adb_monkey(package_name, allow_failure):
            return True
        if self._app_start_adb_am(package_name, activity_name, allow_failure):
            return True

        logger.error('app_start_adb: All trials failed')
        return False

    @retry
    def app_stop_adb(self, package_name=None):
        """
        停止应用。
        使用am force-stop命令强制停止应用。
        
        Args:
            package_name: 要停止的应用包名
        """
        if not package_name:
            package_name = self.package
        self.adb_shell(['am', 'force-stop', package_name])

    @retry
    def dump_hierarchy_adb(self, temp: str = '/data/local/tmp/hierarchy.xml') -> etree._Element:
        """
        获取界面层级结构。
        使用uiautomator dump命令获取当前界面的层级结构。
        
        Args:
            temp: 临时文件路径
            
        Returns:
            etree._Element: 界面层级树
            
        Raises:
            Exception: 当获取层级结构失败时抛出
        """
        # 尝试获取层级结构
        for _ in range(2):
            response = self.adb_shell(['uiautomator', 'dump', '--compressed', temp])
            if 'hierchary' in response:
                # UI hierchary dumped to: /data/local/tmp/hierarchy.xml
                break
            else:
                # <None>
                # 必须杀死uiautomator2
                self.app_stop_adb('com.github.uiautomator')
                self.app_stop_adb('com.github.uiautomator.test')
                continue

        # 从设备读取文件内容
        content = b''
        for chunk in self.adb.sync.iter_content(temp):
            if chunk:
                content += chunk
            else:
                break

        # 使用lxml解析
        hierarchy = etree.fromstring(content)
        return hierarchy
