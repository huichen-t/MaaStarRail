"""
uiautomator2控制模块。
提供通过uiautomator2控制Android设备的功能。
uiautomator2是Google提供的UI自动化测试框架，可以用于控制Android设备。
"""

import time
from dataclasses import dataclass
from functools import wraps
from json.decoder import JSONDecodeError
from subprocess import list2cmdline

import cv2
import numpy as np
import uiautomator2 as u2
from adbutils.errors import AdbError
from lxml import etree

from module.base.utils import *
from module.config_src.server import DICT_PACKAGE_TO_ACTIVITY
from module.device.connection import Connection
from module.device.method.utils import (ImageTruncated, PackageNotInstalled, RETRY_TRIES, handle_adb_error,
                                        handle_unknown_host_service, possible_reasons, retry_sleep)
from module.exception import RequestHumanTakeover
from module.logger import logger


def retry(func):
    """
    重试装饰器。
    当函数执行失败时自动重试，最多重试RETRY_TRIES次。
    处理各种异常情况：
    - ADB连接重置
    - JSON解码错误
    - ADB错误
    - 运行时错误
    - 断言错误
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
        """
        Args:
            self (Uiautomator2):
        """
        init = None
        for _ in range(RETRY_TRIES):
            try:
                if callable(init):
                    time.sleep(retry_sleep(_))
                    init()
                return func(self, *args, **kwargs)
            # Can't handle
            except RequestHumanTakeover:
                break
            # When adb server was killed
            except ConnectionResetError as e:
                logger.error(e)

                def init():
                    self.adb_reconnect()
            # In `device.set_new_command_timeout(604800)`
            # json.decoder.JSONDecodeError: Expecting value: line 1 column 2 (char 1)
            except JSONDecodeError as e:
                logger.error(e)

                def init():
                    self.install_uiautomator2()
            # AdbError
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
            # RuntimeError: USB device 127.0.0.1:5555 is offline
            except RuntimeError as e:
                if handle_adb_error(e):
                    def init():
                        self.adb_reconnect()
                else:
                    break
            # In `assert c.read string(4) == _OKAY`
            # ADB on emulator not enabled
            except AssertionError as e:
                logger.exception(e)
                possible_reasons(
                    'If you are using BlueStacks or LD player or WSA, '
                    'please enable ADB in the settings of your emulator'
                )
                break
            # Package not installed
            except PackageNotInstalled as e:
                logger.error(e)

                def init():
                    self.detect_package()
            # ImageTruncated
            except ImageTruncated as e:
                logger.error(e)

                def init():
                    pass
            # Unknown
            except Exception as e:
                logger.exception(e)

                def init():
                    pass

        logger.critical(f'Retry {func.__name__}() failed')
        raise RequestHumanTakeover

    return retry_wrapper


@dataclass
class ProcessInfo:
    """
    进程信息数据类。
    用于存储进程的详细信息。
    """
    pid: int  # 进程ID
    ppid: int  # 父进程ID
    thread_count: int  # 线程数
    cmdline: str  # 命令行
    name: str  # 进程名称


@dataclass
class ShellBackgroundResponse:
    """
    后台Shell命令响应数据类。
    用于存储后台Shell命令的执行结果。
    """
    success: bool  # 是否成功
    pid: int  # 进程ID
    description: str  # 描述信息


class Uiautomator2(Connection):
    """
    uiautomator2控制类。
    提供通过uiautomator2控制Android设备的各种功能。
    继承自Connection类，实现设备连接的基础功能。
    """

    @retry
    def screenshot_uiautomator2(self):
        """
        通过uiautomator2获取屏幕截图。
        
        Returns:
            np.ndarray: 屏幕截图数据
            
        Raises:
            ImageTruncated: 当图像数据无效时抛出
        """
        image = self.u2.screenshot(format='raw')
        image = np.frombuffer(image, np.uint8)
        if image is None:
            raise ImageTruncated('Empty image after reading from buffer')

        image = cv2.imdecode(image, cv2.IMREAD_COLOR)
        if image is None:
            raise ImageTruncated('Empty image after cv2.imdecode')

        cv2.cvtColor(image, cv2.COLOR_BGR2RGB, dst=image)
        if image is None:
            raise ImageTruncated('Empty image after cv2.cvtColor')

        return image

    @retry
    def click_uiautomator2(self, x, y):
        """
        执行点击操作。
        
        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
        """
        self.u2.click(x, y)

    @retry
    def long_click_uiautomator2(self, x, y, duration=(1, 1.2)):
        """
        执行长按操作。
        
        Args:
            x: 长按位置的x坐标
            y: 长按位置的y坐标
            duration: 长按持续时间范围（秒）
        """
        self.u2.long_click(x, y, duration=duration)

    @retry
    def swipe_uiautomator2(self, p1, p2, duration=0.1):
        """
        执行滑动操作。
        
        Args:
            p1: 起始点坐标
            p2: 结束点坐标
            duration: 滑动持续时间（秒）
        """
        self.u2.swipe(*p1, *p2, duration=duration)

    @retry
    def _drag_along(self, path):
        """
        沿指定路径执行拖拽操作。
        
        Args:
            path: 路径点列表，每个点包含(x, y, sleep)信息
            
        Examples:
            al.drag_along([
                (403, 421, 0.2),
                (821, 326, 0.1),
                (821, 326-10, 0.1),
                (821, 326+10, 0.1),
                (821, 326, 0),
            ])
            等同于:
            al.device.touch.down(403, 421)
            time.sleep(0.2)
            al.device.touch.move(821, 326)
            time.sleep(0.1)
            al.device.touch.move(821, 326-10)
            time.sleep(0.1)
            al.device.touch.move(821, 326+10)
            time.sleep(0.1)
            al.device.touch.up(821, 326)
        """
        length = len(path)
        for index, data in enumerate(path):
            x, y, second = data
            if index == 0:
                self.u2.touch.down(x, y)
                logger.info(point2str(x, y) + ' down')
            elif index - length == -1:
                self.u2.touch.up(x, y)
                logger.info(point2str(x, y) + ' up')
            else:
                self.u2.touch.move(x, y)
                logger.info(point2str(x, y) + ' move')
            self.sleep(second)

    def drag_uiautomator2(self, p1, p2, segments=1, shake=(0, 15), point_random=(-10, -10, 10, 10),
                          shake_random=(-5, -5, 5, 5), swipe_duration=0.25, shake_duration=0.1):
        """
        执行拖拽和抖动操作。
        简单的滑动或拖拽可能效果不好，因为只有两个点。
        添加一些中间点使其更像滑动。
        
        Args:
            p1: 起始点坐标
            p2: 结束点坐标
            segments: 分段数
            shake: 到达终点后的抖动范围
            point_random: 起始点和终点添加的随机偏移范围
            shake_random: 抖动点添加的随机偏移范围
            swipe_duration: 路径点之间的持续时间
            shake_duration: 抖动点之间的持续时间
        """
        p1 = np.array(p1) - random_rectangle_point(point_random)
        p2 = np.array(p2) - random_rectangle_point(point_random)
        path = [(x, y, swipe_duration) for x, y in random_line_segments(p1, p2, n=segments, random_range=point_random)]
        path += [
            (*p2 + shake + random_rectangle_point(shake_random), shake_duration),
            (*p2 - shake - random_rectangle_point(shake_random), shake_duration),
            (*p2, shake_duration)
        ]
        path = [(int(x), int(y), d) for x, y, d in path]
        self._drag_along(path)

    @retry
    def app_current_uiautomator2(self):
        """
        获取当前运行的应用包名。
        
        Returns:
            str: 当前运行的应用包名
        """
        result = self.u2.app_current()
        return result['package']

    @retry
    def _app_start_u2_monkey(self, package_name=None, allow_failure=False):
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
        result = self.u2.shell([
            'monkey', '-p', package_name, '-c',
            'android.intent.category.LAUNCHER', '--pct-syskeys', '0', '1'
        ])
        if 'No activities found' in result.output:
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
    def _app_start_u2_am(self, package_name=None, activity_name=None, allow_failure=False):
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
            try:
                info = self.u2.app_info(package_name)
            except u2.BaseError as e:
                if allow_failure:
                    return False
                # BaseError('package "111" not found')
                elif 'not found' in str(e):
                    logger.error(e)
                    raise PackageNotInstalled(package_name)
                # Unknown error
                else:
                    raise
            activity_name = info['mainActivity']

        cmd = ['am', 'start', '-a', 'android.intent.action.MAIN', '-c',
               'android.intent.category.LAUNCHER', '-n', f'{package_name}/{activity_name}']
        if self.is_local_network_device and self.is_waydroid:
            cmd += ['--windowingMode', '4']
        ret = self.u2.shell(cmd)
        # Invalid activity
        # Starting: Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] cmp=... }
        # Error type 3
        # Error: Activity class {.../...} does not exist.
        if 'Error: Activity class' in ret.output:
            if allow_failure:
                return False
            else:
                logger.error(ret)
                return False
        # Already running
        # Warning: Activity not started, intent has been delivered to currently running top-most instance.
        if 'Warning: Activity not started' in ret.output:
            logger.info('App activity is already started')
            return True
        # Starting: Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] cmp=com.YoStarEN.AzurLane/com.manjuu.azurlane.MainActivity }
        # java.lang.SecurityException: Permission Denial: starting Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] flg=0x10000000 cmp=com.YoStarEN.AzurLane/com.manjuu.azurlane.MainActivity } from null (pid=5140, uid=2000) not exported from uid 10064
        #         at android.os.Parcel.readException(Parcel.java:1692)
        #         at android.os.Parcel.readException(Parcel.java:1645)
        #         at android.app.ActivityManagerProxy.startActivityAsUser(ActivityManagerNative.java:3152)
        #         at com.android.commands.am.Am.runStart(Am.java:643)
        #         at com.android.commands.am.Am.onRun(Am.java:394)
        #         at com.android.internal.os.BaseCommand.run(BaseCommand.java:51)
        #         at com.android.commands.am.Am.main(Am.java:124)
        #         at com.android.internal.os.RuntimeInit.nativeFinishInit(Native Method)
        #         at com.android.internal.os.RuntimeInit.main(RuntimeInit.java:290)
        if 'Permission Denial' in ret.output:
            if allow_failure:
                return False
            else:
                logger.error(ret)
                logger.error('Permission Denial while starting app, probably because activity invalid')
                return False
        # Success
        # Starting: Intent...
        return True

    # No @retry decorator since _app_start_adb_am and _app_start_adb_monkey have @retry already
    # @retry
    def app_start_uiautomator2(self, package_name=None, activity_name=None, allow_failure=False):
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
            if self._app_start_u2_am(package_name, activity_name, allow_failure):
                return True
        if self._app_start_u2_monkey(package_name, allow_failure):
            return True
        if self._app_start_u2_am(package_name, activity_name, allow_failure):
            return True

        logger.error('app_start_uiautomator2: All trials failed')
        return False

    @retry
    def app_stop_uiautomator2(self, package_name=None):
        """
        停止应用。
        
        Args:
            package_name: 要停止的应用包名
        """
        if not package_name:
            package_name = self.package
        self.u2.app_stop(package_name)

    @retry
    def dump_hierarchy_uiautomator2(self) -> etree._Element:
        """
        获取界面层级结构。
        
        Returns:
            etree._Element: 界面层级树
        """
        content = self.u2.dump_hierarchy(compressed=False)
        # print(content)
        hierarchy = etree.fromstring(content.encode('utf-8'))
        return hierarchy

    def uninstall_uiautomator2(self):
        """
        卸载uiautomator2相关文件。
        删除设备上的uiautomator2相关文件。
        """
        logger.info('Removing uiautomator2')
        for file in [
            'app-uiautomator.apk',
            'app-uiautomator-test.apk',
            'minitouch',
            'minitouch.so',
            'atx-agent',
        ]:
            self.adb_shell(["rm", f"/data/local/tmp/{file}"])

    @retry
    def resolution_uiautomator2(self, cal_rotation=True) -> t.Tuple[int, int]:
        """
        获取设备分辨率。
        比u2.window_size()更快，因为后者会调用两次`dumpsys display`。
        
        Args:
            cal_rotation: 是否计算旋转
            
        Returns:
            (width, height): 屏幕宽度和高度
        """
        info = self.u2.http.get('/info').json()
        w, h = info['display']['width'], info['display']['height']
        if cal_rotation:
            rotation = self.get_orientation()
            if (w > h) != (rotation % 2 == 1):
                w, h = h, w
        return w, h

    def resolution_check_uiautomator2(self):
        """
        检查设备分辨率。
        Alas不会主动检查分辨率，而是检查截图的宽度和高度。
        但是某些截图方法不提供设备分辨率，所以在这里检查。
        
        Returns:
            (width, height): 屏幕宽度和高度
            
        Raises:
            RequestHumanTakeover: 当分辨率不是1280x720时抛出
        """
        width, height = self.resolution_uiautomator2()
        logger.attr('Screen_size', f'{width}x{height}')
        if width == 1280 and height == 720:
            return (width, height)
        if width == 720 and height == 1280:
            return (width, height)

        logger.critical(f'Resolution not supported: {width}x{height}')
        logger.critical('Please set emulator resolution to 1280x720')
        raise RequestHumanTakeover

    @retry
    def proc_list_uiautomator2(self) -> t.List[ProcessInfo]:
        """
        获取当前进程信息列表。
        
        Returns:
            List[ProcessInfo]: 进程信息列表
        """
        resp = self.u2.http.get("/proc/list", timeout=10)
        resp.raise_for_status()
        result = [
            ProcessInfo(
                pid=proc['pid'],
                ppid=proc['ppid'],
                thread_count=proc['threadCount'],
                cmdline=' '.join(proc['cmdline']) if proc['cmdline'] is not None else '',
                name=proc['name'],
            ) for proc in resp.json()
        ]
        return result

    @retry
    def u2_shell_background(self, cmdline, timeout=10) -> ShellBackgroundResponse:
        """
        在后台运行Shell命令。
        
        注意：这个函数总是返回成功响应，
        因为这是ATX中一个未测试的隐藏方法。
        
        Args:
            cmdline: 要执行的命令
            timeout: 超时时间（秒）
            
        Returns:
            ShellBackgroundResponse: 命令执行结果
        """
        if isinstance(cmdline, (list, tuple)):
            cmdline = list2cmdline(cmdline)
        elif isinstance(cmdline, str):
            cmdline = cmdline
        else:
            raise TypeError("cmdargs type invalid", type(cmdline))

        data = dict(command=cmdline, timeout=str(timeout))
        ret = self.u2.http.post("/shell/background", data=data, timeout=timeout + 10)
        ret.raise_for_status()

        resp = ret.json()
        resp = ShellBackgroundResponse(
            success=bool(resp.get('success', False)),
            pid=resp.get('pid', 0),
            description=resp.get('description', '')
        )
        return resp
