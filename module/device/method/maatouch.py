"""
MaaTouch控制模块。
提供通过MaaTouch控制Android设备的功能。
MaaTouch是一个类似scrcpy和minitouch的触摸控制工具，提供更精确的触摸控制。
https://github.com/MaaAssistantArknights/MaaTouch
"""

import socket
import threading
import time
from functools import wraps

import numpy as np
from adbutils.errors import AdbError

from module.base.decorator import cached_property, del_cached_property, has_cached_property
from module.base.timer import Timer
from module.base.utils import *
from module.device.connection import Connection
from module.device.method.minitouch import CommandBuilder, insert_swipe
from module.device.method.utils import RETRY_TRIES, handle_adb_error, handle_unknown_host_service, retry_sleep
from module.exception import RequestHumanTakeover
from module.logger import logger


def retry(func):
    """
    重试装饰器。
    当函数执行失败时自动重试，最多重试RETRY_TRIES次。
    处理各种异常情况：
    - ADB连接重置
    - 模拟器关闭
    - ADB错误
    - MaaTouch未安装
    - 管道破裂
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
                    del_cached_property(self, '_maatouch_builder')
            # 模拟器关闭
            except ConnectionAbortedError as e:
                logger.error(e)

                def init():
                    self.adb_reconnect()
                    del_cached_property(self, '_maatouch_builder')
            # ADB错误
            except AdbError as e:
                if handle_adb_error(e):
                    def init():
                        self.adb_reconnect()
                        del_cached_property(self, '_maatouch_builder')
                elif handle_unknown_host_service(e):
                    def init():
                        self.adb_start_server()
                        self.adb_reconnect()
                        del_cached_property(self, '_maatouch_builder')
                else:
                    break
            # MaaTouch未安装
            except MaaTouchNotInstalledError as e:
                logger.error(e)

                def init():
                    self.maatouch_install()
                    del_cached_property(self, '_maatouch_builder')
            # 管道破裂
            except BrokenPipeError as e:
                logger.error(e)

                def init():
                    del_cached_property(self, '_maatouch_builder')
            # 未知错误
            except Exception as e:
                logger.exception(e)

                def init():
                    pass

        logger.critical(f'Retry {func.__name__}() failed')
        raise RequestHumanTakeover

    return retry_wrapper


class MaatouchBuilder(CommandBuilder):
    """
    MaaTouch命令构建器。
    继承自CommandBuilder，用于构建MaaTouch控制命令。
    """
    def __init__(self, device, contact=0, handle_orientation=False):
        """
        初始化MaaTouch命令构建器。
        
        Args:
            device: MaaTouch设备实例
            contact: 触摸点ID
            handle_orientation: 是否处理屏幕方向
        """
        super().__init__(device, contact, handle_orientation)

    def send(self):
        """
        发送构建的命令到设备。
        
        Returns:
            命令执行结果
        """
        return self.device.maatouch_send(builder=self)


class MaaTouchNotInstalledError(Exception):
    """MaaTouch未安装异常"""
    pass


class MaaTouch(Connection):
    """
    MaaTouch控制类。
    实现类似scrcpy的功能，提供类似minitouch的接口。
    用于精确控制Android设备的触摸操作。
    """
    max_x: int  # 屏幕最大X坐标
    max_y: int  # 屏幕最大Y坐标
    _maatouch_stream: socket.socket = None  # MaaTouch连接流
    _maatouch_stream_storage = None  # MaaTouch流存储
    _maatouch_init_thread = None  # MaaTouch初始化线程
    _maatouch_orientation: int = None  # MaaTouch屏幕方向

    @cached_property
    @retry
    def _maatouch_builder(self):
        """
        获取MaaTouch命令构建器。
        如果未初始化，会先进行初始化。
        
        Returns:
            MaatouchBuilder: MaaTouch命令构建器实例
        """
        self.maatouch_init()
        return MaatouchBuilder(self)

    @property
    def maatouch_builder(self):
        """
        获取MaaTouch命令构建器。
        等待初始化线程完成。
        
        Returns:
            MaatouchBuilder: MaaTouch命令构建器实例
        """
        # 等待初始化线程
        if self._maatouch_init_thread is not None:
            self._maatouch_init_thread.join()
            del self._maatouch_init_thread
            self._maatouch_init_thread = None

        return self._maatouch_builder

    def early_maatouch_init(self):
        """
        提前初始化MaaTouch连接。
        在Alas实例开始截图时启动一个线程来初始化MaaTouch连接，
        这样可以加快第一次点击的速度（约0.2~0.4秒）。
        """
        if has_cached_property(self, '_maatouch_builder'):
            return

        def early_maatouch_init_func():
            _ = self._maatouch_builder

        thread = threading.Thread(target=early_maatouch_init_func, daemon=True)
        self._maatouch_init_thread = thread
        thread.start()

    def on_orientation_change_maatouch(self):
        """
        处理屏幕方向变化。
        MaaTouch在启动时会缓存设备方向，
        当方向发生变化时需要重新初始化。
        """
        if self._maatouch_orientation is None:
            return
        if self.orientation == self._maatouch_orientation:
            return

        logger.info(f'Orientation changed {self._maatouch_orientation} => {self.orientation}, re-init MaaTouch')
        del_cached_property(self, '_maatouch_builder')
        self.early_maatouch_init()

    def maatouch_init(self):
        """
        初始化MaaTouch连接。
        设置屏幕参数并建立与MaaTouch服务器的连接。
        """
        logger.hr('MaaTouch init')
        max_x, max_y = 1280, 720  # 默认屏幕分辨率
        max_contacts = 2  # 最大触摸点数
        max_pressure = 50  # 最大压力值

        # 尝试关闭已存在的连接
        if self._maatouch_stream is not None:
            try:
                self._maatouch_stream.close()
            except Exception as e:
                logger.error(e)
            del self._maatouch_stream
        if self._maatouch_stream_storage is not None:
            del self._maatouch_stream_storage

        # MaaTouch在启动时会缓存设备方向
        super(MaaTouch, self).get_orientation()
        self._maatouch_orientation = self.orientation

        # 启动MaaTouch服务
        stream = self.adb_shell(
            ['CLASSPATH=/data/local/tmp/maatouch', 'app_process', '/', 'com.shxyke.MaaTouch.App'],
            stream=True,
            recvall=False
        )
        # 防止shell流被删除导致socket关闭
        self._maatouch_stream_storage = stream
        stream = stream.conn
        stream.settimeout(10)
        self._maatouch_stream = stream

        # 等待MaaTouch服务响应
        retry_timeout = Timer(5).start()
        while 1:
            socket_out = stream.makefile()

            # 获取MaaTouch服务器信息
            out = socket_out.readline().replace("\n", "").replace("\r", "")
            logger.info(out)
            if out.strip() == 'Aborted':
                stream.close()
                raise MaaTouchNotInstalledError(
                    'Received "Aborted" MaaTouch, '
                    'probably because MaaTouch is not installed'
                )
            try:
                _, max_contacts, max_x, max_y, max_pressure = out.split(" ")
                break
            except ValueError:
                stream.close()
                if retry_timeout.reached():
                    raise MaaTouchNotInstalledError(
                        'Received empty data from MaaTouch, '
                        'probably because MaaTouch is not installed'
                    )
                else:
                    # MaaTouch可能还没有完全启动
                    self.sleep(1)
                    continue

        # 设置屏幕参数
        self.max_x = int(max_x)
        self.max_y = int(max_y)

        # 获取进程ID
        out = socket_out.readline().replace("\n", "").replace("\r", "")
        logger.info(out)

        logger.info(
            "MaaTouch stream connected"
        )
        logger.info(
            "max_contact: {}; max_x: {}; max_y: {}; max_pressure: {}".format(
                max_contacts, max_x, max_y, max_pressure
            )
        )

    def maatouch_send(self, builder: MaatouchBuilder):
        """
        发送MaaTouch命令到设备。
        
        Args:
            builder: MaaTouch命令构建器实例
        """
        content = builder.to_minitouch()
        byte_content = content.encode('utf-8')
        self._maatouch_stream.sendall(byte_content)
        self._maatouch_stream.recv(0)
        self.sleep(self.maatouch_builder.delay / 1000 + builder.DEFAULT_DELAY)
        builder.clear()

    def maatouch_install(self):
        """
        安装MaaTouch到设备。
        将本地MaaTouch文件推送到设备。
        """
        logger.hr('MaaTouch install')
        self.adb_push(self.config.MAATOUCH_FILEPATH_LOCAL, self.config.MAATOUCH_FILEPATH_REMOTE)

    def maatouch_uninstall(self):
        """
        从设备卸载MaaTouch。
        删除设备上的MaaTouch文件。
        """
        logger.hr('MaaTouch uninstall')
        self.adb_shell(["rm", self.config.MAATOUCH_FILEPATH_REMOTE])

    @retry
    def click_maatouch(self, x, y):
        """
        执行点击操作。
        
        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
        """
        builder = self.maatouch_builder
        builder.down(x, y).commit()
        builder.up().commit()
        builder.send()

    @retry
    def long_click_maatouch(self, x, y, duration=1.0):
        """
        执行长按操作。
        
        Args:
            x: 长按位置的x坐标
            y: 长按位置的y坐标
            duration: 长按持续时间（秒）
        """
        duration = int(duration * 1000)
        builder = self.maatouch_builder
        builder.down(x, y).commit().wait(duration)
        builder.up().commit()
        builder.send()

    @retry
    def swipe_maatouch(self, p1, p2):
        """
        执行滑动操作。
        
        Args:
            p1: 起始点坐标
            p2: 结束点坐标
        """
        points = insert_swipe(p0=p1, p3=p2)
        builder = self.maatouch_builder

        builder.down(*points[0]).commit().wait(10)
        builder.send()

        for point in points[1:]:
            builder.move(*point).commit().wait(10)
        builder.send()

        builder.up().commit()
        builder.send()

    @retry
    def drag_maatouch(self, p1, p2, point_random=(-10, -10, 10, 10)):
        """
        执行拖拽操作。
        
        Args:
            p1: 起始点坐标
            p2: 结束点坐标
            point_random: 随机偏移范围
        """
        p1 = np.array(p1) - random_rectangle_point(point_random)
        p2 = np.array(p2) - random_rectangle_point(point_random)
        points = insert_swipe(p0=p1, p3=p2, speed=20)
        builder = self.maatouch_builder

        builder.down(*points[0]).commit().wait(10)
        builder.send()

        for point in points[1:]:
            builder.move(*point).commit().wait(10)
        builder.send()

        builder.move(*p2).commit().wait(140)
        builder.move(*p2).commit().wait(140)
        builder.send()

        builder.up().commit()
        builder.send()


if __name__ == '__main__':
    self = MaaTouch('src')
    self.maatouch_uninstall()