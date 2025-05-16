"""
设备管理器模块。
提供全局设备连接管理接口。
使用单例模式确保设备管理器实例的唯一性。
"""

import os
import re
import time
import psutil
from typing import Optional, Dict, Any, List, Tuple
from threading import Thread, Event
from lxml import etree

import adbutils
import uiautomator2 as u2
from adbutils import AdbClient, AdbDevice, ForwardItem, ReverseItem
from adbutils.errors import AdbError

from module.base.decorator import cached_property
from module.base.logger import logger
from module.base.timer import Timer
from module.device.device_utils import DeviceUtils
from module.device.method.utils import HierarchyButton, random_port
from module.exception import RequestHumanTakeover, ScriptError
from module.device.utils.image_utils import ImageUtils


class PackageNotInstalled(Exception):
    """包未安装异常"""
    pass


class DeviceMonitor:
    """设备监控器类，用于监控设备状态"""
    
    def __init__(self, device_manager: 'DeviceManager'):
        self.device_manager = device_manager
        self._stop_event = Event()
        self._monitor_thread: Optional[Thread] = None
        self._last_check_time = 0
        self._check_interval = 5  # 检查间隔（秒）
        self._status = {
            'connected': False,
            'last_check': 0,
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'battery_level': 0,
            'battery_temperature': 0,
            'network_status': 'unknown',
            'adb_status': 'unknown',
            'u2_status': 'unknown'
        }
    
    def start(self) -> None:
        """启动监控"""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return
            
        self._stop_event.clear()
        self._monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("设备监控已启动")
    
    def stop(self) -> None:
        """停止监控"""
        if self._monitor_thread is None:
            return
            
        self._stop_event.set()
        self._monitor_thread.join()
        self._monitor_thread = None
        logger.info("设备监控已停止")
    
    def _monitor_loop(self) -> None:
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                self._check_device_status()
                time.sleep(self._check_interval)
            except Exception as e:
                logger.error(f"设备监控出错: {str(e)}")
                time.sleep(1)
    
    def _check_device_status(self) -> None:
        """检查设备状态"""
        if self.device_manager._serial is None:
            self._status['connected'] = False
            return
            
        try:
            # 检查ADB连接状态
            self._status['adb_status'] = 'connected' if self.device_manager.adb_client.devices() else 'disconnected'
            
            # 检查uiautomator2状态
            try:
                self.device_manager.u2.info
                self._status['u2_status'] = 'connected'
            except Exception:
                self._status['u2_status'] = 'disconnected'
            
            # 获取设备信息
            device_info = self.device_manager.get_device_info()
            self._status['connected'] = True
            self._status['last_check'] = time.time()
            
            # 获取性能指标
            self._get_performance_metrics()
            
            # 获取电池信息
            self._get_battery_info()
            
            # 获取网络状态
            self._get_network_status()
            
        except Exception as e:
            logger.error(f"检查设备状态失败: {str(e)}")
            self._status['connected'] = False
    
    def _get_performance_metrics(self) -> None:
        """获取性能指标"""
        try:
            # 获取CPU使用率
            cpu_info = self.device_manager.adb.shell('top -n 1 | grep -E "^CPU"')
            if cpu_info:
                cpu_usage = re.search(r'(\d+)%', cpu_info)
                if cpu_usage:
                    self._status['cpu_usage'] = float(cpu_usage.group(1))
            
            # 获取内存使用率
            mem_info = self.device_manager.adb.shell('cat /proc/meminfo')
            if mem_info:
                total = re.search(r'MemTotal:\s+(\d+)', mem_info)
                free = re.search(r'MemFree:\s+(\d+)', mem_info)
                if total and free:
                    total_mem = int(total.group(1))
                    free_mem = int(free.group(1))
                    self._status['memory_usage'] = (total_mem - free_mem) / total_mem * 100
        except Exception as e:
            logger.error(f"获取性能指标失败: {str(e)}")
    
    def _get_battery_info(self) -> None:
        """获取电池信息"""
        try:
            battery_info = self.device_manager.adb.shell('dumpsys battery')
            if battery_info:
                level = re.search(r'level: (\d+)', battery_info)
                temperature = re.search(r'temperature: (\d+)', battery_info)
                if level:
                    self._status['battery_level'] = int(level.group(1))
                if temperature:
                    self._status['battery_temperature'] = int(temperature.group(1)) / 10.0
        except Exception as e:
            logger.error(f"获取电池信息失败: {str(e)}")
    
    def _get_network_status(self) -> None:
        """获取网络状态"""
        try:
            network_info = self.device_manager.adb.shell('dumpsys connectivity')
            if network_info:
                if 'CONNECTED' in network_info:
                    self._status['network_status'] = 'connected'
                elif 'DISCONNECTED' in network_info:
                    self._status['network_status'] = 'disconnected'
                else:
                    self._status['network_status'] = 'unknown'
        except Exception as e:
            logger.error(f"获取网络状态失败: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取设备状态"""
        return self._status.copy()
    
    def is_healthy(self) -> bool:
        """检查设备是否健康"""
        if not self._status['connected']:
            return False
            
        # 检查关键指标
        if self._status['cpu_usage'] > 90:  # CPU使用率过高
            return False
        if self._status['memory_usage'] > 90:  # 内存使用率过高
            return False
        if self._status['battery_level'] < 10:  # 电量过低
            return False
        if self._status['battery_temperature'] > 45:  # 温度过高
            return False
        if self._status['network_status'] != 'connected':  # 网络未连接
            return False
        if self._status['adb_status'] != 'connected':  # ADB未连接
            return False
        if self._status['u2_status'] != 'connected':  # uiautomator2未连接
            return False
            
        return True


class DeviceManager:
    """
    设备管理器类，使用单例模式管理所有设备实例。
    
    主要功能：
    - 统一管理所有设备连接
    - 提供全局访问接口
    - 确保设备连接的唯一性
    """
    
    _instance: Optional['DeviceManager'] = None
    _initialized: bool = False
    
    # 支持的adb可执行文件路径列表，按优先级排序
    ADB_BINARY_PATHS = [
        './bin/adb/adb.exe',  # 项目内置ADB
        './toolkit/Lib/site-packages/adbutils/binaries/adb.exe',  # 工具包ADB
        '/usr/bin/adb'  # 系统ADB
    ]
    
    def __new__(cls) -> 'DeviceManager':
        """
        实现单例模式。
        
        Returns:
            DeviceManager: 设备管理器实例
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """
        初始化设备管理器。
        确保只初始化一次。
        """
        if not self._initialized:
            self._serial: Optional[str] = None
            self._resources: List[Any] = []
            self._monitor = DeviceMonitor(self)
            self._hierarchy_interval = Timer(0.1)
            self._hierarchy: Optional[etree._Element] = None
            self._package: Optional[str] = None
            self._initialized = True
            logger.info("设备管理器初始化成功")
    
    @property
    def serial(self) -> Optional[str]:
        """
        获取当前设备序列号。
        
        Returns:
            Optional[str]: 当前设备序列号，如果未连接则返回None
        """
        return self._serial
    
    @property
    def package(self) -> Optional[str]:
        """
        获取当前目标应用包名。
        
        Returns:
            Optional[str]: 当前目标应用包名
        """
        return self._package
    
    @package.setter
    def package(self, value: str) -> None:
        """
        设置当前目标应用包名。
        
        Args:
            value (str): 应用包名
        """
        self._package = value
    
    def connect_device(self, serial: str) -> 'DeviceManager':
        """
        连接指定设备。
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            DeviceManager: 设备管理器实例
            
        Raises:
            Exception: 连接失败时抛出异常
        """
        try:
            # 如果已经连接了设备，先断开
            if self._serial is not None:
                self.disconnect_device()
            
            # 标准化序列号
            serial = DeviceUtils.revise_serial(serial)
            
            # 验证序列号
            if not DeviceUtils.is_valid_serial(serial):
                raise ValueError(f"无效的设备序列号: {serial}")
            
            # 设置序列号并初始化连接
            self._serial = serial
            self._init_connection()
            
            # 启动设备监控
            self._monitor.start()
            
            logger.info(f"设备连接成功: {serial}")
            return self
            
        except Exception as e:
            logger.error(f"设备连接失败: {str(e)}")
            raise
    
    def disconnect_device(self) -> None:
        """
        断开当前设备连接。
        """
        if self._serial is not None:
            try:
                # 停止设备监控
                self._monitor.stop()
                
                # 释放所有资源
                self.release_resources()
                self._serial = None
                logger.info("设备已断开连接")
            except Exception as e:
                logger.error(f"断开设备连接失败: {str(e)}")
                raise
    
    def _init_connection(self):
        """初始化设备连接"""
        # 初始化ADB客户端
        logger.attr('AdbBinary', self.adb_binary)
        # 设置adbutils使用自定义adb路径
        adbutils.adb_path = lambda: self.adb_binary
        # 移除全局代理，避免uiautomator2走代理
        for k in list(os.environ.keys()):
            if k.lower().endswith('_proxy'):
                del os.environ[k]
        # 缓存adb_client
        _ = self.adb_client
    
    def add_resource(self, resource: Any) -> None:
        """
        添加需要管理的资源。
        
        Args:
            resource (Any): 需要管理的资源对象
        """
        self._resources.append(resource)
    
    def release_resources(self) -> None:
        """释放所有资源"""
        for resource in self._resources:
            try:
                if hasattr(resource, 'release'):
                    resource.release()
                elif hasattr(resource, 'close'):
                    resource.close()
            except Exception as e:
                logger.error(f"释放资源失败: {str(e)}")
        self._resources.clear()
    
    def adb_forward(self, remote: str) -> int:
        """
        执行`adb forward <local> <remote>`命令。
        在FORWARD_PORT_RANGE范围内选择一个随机端口或重用现有的forward，
        并移除多余的forward。
        
        Args:
            remote (str): 远程地址，可以是以下格式：
                - tcp:<port>
                - localabstract:<unix domain socket name>
                - localreserved:<unix domain socket name>
                - localfilesystem:<unix domain socket name>
                - dev:<character device name>
                - jdwp:<process pid> (仅远程)
                
        Returns:
            int: 端口号
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        port = 0
        for forward in self.adb.forward_list():
            if forward.serial == self._serial and forward.remote == remote and forward.local.startswith('tcp:'):
                if not port:
                    logger.info(f'Reuse forward: {forward}')
                    port = int(forward.local[4:])
                else:
                    logger.info(f'Remove redundant forward: {forward}')
                    self.adb_forward_remove(forward.local)

        if port:
            return port
        else:
            # Create new forward
            port = random_port((10000, 20000))  # 使用合适的端口范围
            forward = ForwardItem(self._serial, f'tcp:{port}', remote)
            logger.info(f'Create forward: {forward}')
            self.adb.forward(forward.local, forward.remote)
            return port
    
    def adb_reverse(self, remote: str) -> int:
        """
        执行`adb reverse`命令，设置端口转发。
        
        Args:
            remote (str): 远程地址
            
        Returns:
            int: 端口号
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        port = 0
        for reverse in self.adb.reverse_list():
            if reverse.remote == remote and reverse.local.startswith('tcp:'):
                if not port:
                    logger.info(f'Reuse reverse: {reverse}')
                    port = int(reverse.local[4:])
                else:
                    logger.info(f'Remove redundant forward: {reverse}')
                    self.adb_forward_remove(reverse.local)

        if port:
            return port
        else:
            # Create new reverse
            port = random_port((10000, 20000))  # 使用合适的端口范围
            reverse = ReverseItem(f'tcp:{port}', remote)
            logger.info(f'Create reverse: {reverse}')
            self.adb.reverse(reverse.local, reverse.remote)
            return port
    
    def adb_forward_remove(self, local: str) -> None:
        """
        移除端口转发，相当于`adb -s <serial> forward --remove <local>`。
        当移除不存在的forward时不会抛出错误。
        
        Args:
            local (str): 本地地址，如'tcp:2437'
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        try:
            with self.adb_client._connect() as c:
                list_cmd = f"host-serial:{self._serial}:killforward:{local}"
                c.send_command(list_cmd)
                c.check_okay()
        except AdbError as e:
            # No error raised when removing a non-existed forward
            # adbutils.errors.AdbError: listener 'tcp:8888' not found
            msg = str(e)
            if re.search(r'listener .*? not found', msg):
                logger.warning(f'{type(e).__name__}: {msg}')
            else:
                raise
    
    def adb_reverse_remove(self, local: str) -> None:
        """
        移除反向端口转发，相当于`adb -s <serial> reverse --remove <local>`。
        当移除不存在的reverse时不会抛出错误。
        
        Args:
            local (str): 本地地址，如'tcp:2437'
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        try:
            with self.adb_client._connect() as c:
                c.send_command(f"host:transport:{self._serial}")
                c.check_okay()
                list_cmd = f"reverse:killforward:{local}"
                c.send_command(list_cmd)
                c.check_okay()
        except AdbError as e:
            # No error raised when removing a non-existed forward
            # adbutils.errors.AdbError: listener 'tcp:8888' not found
            msg = str(e)
            if re.search(r'listener .*? not found', msg):
                logger.warning(f'{type(e).__name__}: {msg}')
            else:
                raise
    
    @cached_property
    def adb_binary(self) -> str:
        """
        获取adb可执行文件路径。
        
        Returns:
            str: adb可执行文件路径
        """
        # 检查常用路径
        for file in self.ADB_BINARY_PATHS:
            if os.path.exists(file):
                return os.path.abspath(file)

        # 检查python环境
        import sys
        file = os.path.join(sys.executable, '../Lib/site-packages/adbutils/binaries/adb.exe')
        file = os.path.abspath(file).replace('\\', '/')
        if os.path.exists(file):
            return file

        # 使用系统PATH中的adb
        return 'adb'
    
    @cached_property
    def adb_client(self) -> AdbClient:
        """
        获取AdbClient对象。
        
        Returns:
            AdbClient: adb客户端对象
        """
        host = '127.0.0.1'
        port = 5037

        env = os.environ.get('ANDROID_ADB_SERVER_PORT', None)
        if env is not None:
            try:
                port = int(env)
            except ValueError:
                logger.warning(f'Invalid environ variable ANDROID_ADB_SERVER_PORT={port}, using default port')

        logger.attr('AdbClient', f'AdbClient({host}, {port})')
        return AdbClient(host, port)
    
    @cached_property
    def adb(self) -> AdbDevice:
        """
        获取AdbDevice对象。
        
        Returns:
            AdbDevice: adb设备对象
            
        Raises:
            Exception: 未连接设备时抛出异常
        """
        if self._serial is None:
            raise Exception("未连接设备")
        return AdbDevice(self.adb_client, self._serial)
    
    @cached_property
    def u2(self) -> u2.Device:
        """
        获取uiautomator2设备对象。
        
        Returns:
            u2.Device: uiautomator2设备对象
            
        Raises:
            Exception: 未连接设备时抛出异常
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        if DeviceUtils.is_over_http(self._serial):
            device = u2.connect(self._serial)
        else:
            if self._serial.startswith('emulator-') or self._serial.startswith('127.0.0.1:'):
                device = u2.connect_usb(self._serial)
            else:
                device = u2.connect(self._serial)

        # 设置命令超时时间，防止连接断开
        device.set_new_command_timeout(604800)

        logger.attr('u2.Device', f'Device(atx_agent_url={device._get_atx_agent_url()})')
        return device
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        获取设备信息。
        
        Returns:
            Dict[str, Any]: 设备信息字典
            
        Raises:
            Exception: 未连接设备时抛出异常
        """
        if self._serial is None:
            raise Exception("未连接设备")
        
        return {
            'serial': self._serial,
            'port': DeviceUtils.extract_port(self._serial),
            'is_emulator': DeviceUtils.is_emulator(self._serial),
            'is_network_device': DeviceUtils.is_network_device(self._serial),
            'is_over_http': DeviceUtils.is_over_http(self._serial),
            'device_type': DeviceUtils.get_device_type(self._serial),
            'adb_path': self.adb_binary
        }

    def list_package(self, show_log: bool = True) -> List[str]:
        """
        获取设备上所有已安装的包。
        优先使用dumpsys命令以加快速度。
        
        Args:
            show_log (bool): 是否显示日志
            
        Returns:
            List[str]: 包名列表
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        # 80ms
        if show_log:
            logger.info('Get package list')
        output = self.adb.shell(r'dumpsys package | grep "Package \["')
        packages = re.findall(r'Package \[([^\s]+)\]', output)
        if len(packages):
            return packages

        # 200ms
        if show_log:
            logger.info('Get package list')
        output = self.adb.shell(['pm', 'list', 'packages'])
        packages = re.findall(r'package:([^\s]+)', output)
        return packages

    def list_known_packages(self, show_log: bool = True) -> List[str]:
        """
        获取已知的包列表。
        
        Args:
            show_log (bool): 是否显示日志
            
        Returns:
            List[str]: 包名列表
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        packages = self.list_package(show_log=show_log)
        # TODO: 从配置中获取有效包名列表
        valid_packages = []  # 这里需要从配置中获取
        cloud_packages = []  # 这里需要从配置中获取
        packages = [p for p in packages if p in valid_packages or p in cloud_packages]
        return packages

    def detect_package(self, set_config: bool = True) -> str:
        """
        检测设备上所有可能的包。
        显示与给定关键字匹配的包。
        
        Args:
            set_config (bool): 是否设置配置
            
        Returns:
            str: 检测到的包名
            
        Raises:
            RequestHumanTakeover: 当无法确定使用哪个包时抛出
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        logger.hr('Detect package')
        packages = self.list_known_packages()

        # 显示包
        logger.info(f'Here are the available packages in device "{self._serial}", '
                    f'copy to Alas.Emulator.PackageName to use it')
        if len(packages):
            for package in packages:
                logger.info(package)
        else:
            logger.info(f'No available packages on device "{self._serial}"')

        # 自动包检测
        if len(packages) == 0:
            logger.critical(f'No Star Rail package found, '
                            f'please confirm Star Rail has been installed on device "{self._serial}"')
            raise RequestHumanTakeover
        if len(packages) == 1:
            logger.info('Auto package detection found only one package, using it')
            package = packages[0]
            # 设置配置
            if set_config:
                # TODO: 更新配置
                pass
            return package
        else:
            # TODO: 从配置中获取云游戏标志
            is_cloud_game = False
            if is_cloud_game:
                # TODO: 从配置中获取云游戏包名列表
                cloud_packages = []
                packages = [p for p in packages if p in cloud_packages]
                if len(packages) == 1:
                    logger.info('Auto package detection found only one package, using it')
                    package = packages[0]
                    if set_config:
                        # TODO: 更新配置
                        pass
                    return package
            else:
                # TODO: 从配置中获取普通包名列表
                valid_packages = []
                packages = [p for p in packages if p in valid_packages]
                if len(packages) == 1:
                    logger.info('Auto package detection found only one package, using it')
                    package = packages[0]
                    if set_config:
                        # TODO: 更新配置
                        pass
                    return package
            logger.critical(
                f'Multiple Star Rail packages found, auto package detection cannot decide which to choose, '
                'please copy one of the available devices listed above to Alas.Emulator.PackageName')
            raise RequestHumanTakeover

    def install_uiautomator2(self) -> None:
        """
        初始化uiautomator2并移除minicap。
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        logger.info('Install uiautomator2')
        init = u2.init.Initer(self.adb, loglevel=logging.DEBUG)
        # MuMu X has no ro.product.cpu.abi, pick abi from ro.product.cpu.abilist
        if init.abi not in ['x86_64', 'x86', 'arm64-v8a', 'armeabi-v7a', 'armeabi']:
            init.abi = init.abis[0]
        init.set_atx_agent_addr('127.0.0.1:7912')
        try:
            init.install()
        except ConnectionError:
            u2.init.GITHUB_BASEURL = 'http://tool.appetizer.io/openatx'
            init.install()
        self.uninstall_minicap()

    def uninstall_minicap(self) -> None:
        """
        卸载minicap，因为某些模拟器上minicap无法工作或会发送压缩图像。
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        logger.info('Removing minicap')
        self.adb.shell(["rm", "/data/local/tmp/minicap"])
        self.adb.shell(["rm", "/data/local/tmp/minicap.so"])

    def restart_atx(self) -> None:
        """
        重启ATX。
        由于minitouch只支持一个连接，重启ATX以踢掉现有连接。
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        if DeviceUtils.is_over_http(self._serial):
            logger.warning(
                f'When connecting a device over http: {self._serial} '
                f'restart_atx() is skipped, you may need to restart ATX manually'
            )
            return
            
        logger.info('Restart ATX')
        atx_agent_path = '/data/local/tmp/atx-agent'
        self.adb.shell([atx_agent_path, 'server', '--stop'])
        self.adb.shell([atx_agent_path, 'server', '--nouia', '-d', '--addr', '127.0.0.1:7912'])

    def get_device_status(self) -> Dict[str, Any]:
        """
        获取设备状态信息。
        
        Returns:
            Dict[str, Any]: 设备状态信息
        """
        return self._monitor.get_status()
    
    def is_device_healthy(self) -> bool:
        """
        检查设备是否健康。
        
        Returns:
            bool: 设备是否健康
        """
        return self._monitor.is_healthy()

    def app_current(self) -> str:
        """
        获取当前运行的应用包名。
        根据不同的控制方法选择相应的实现。
        
        Returns:
            str: 当前运行的应用包名
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        if DeviceUtils.is_wsa(self._serial):
            package = self._app_current_wsa()
        elif DeviceUtils.is_uiautomator2_supported(self._serial):
            package = self._app_current_uiautomator2()
        else:
            package = self._app_current_adb()
        package = package.strip(' \t\r\n')
        return package
    
    def _app_current_wsa(self) -> str:
        """WSA方式获取当前应用包名"""
        output = self.adb.shell(['dumpsys', 'window', 'windows', '|', 'grep', 'mCurrentFocus'])
        match = re.search(r'[a-zA-Z0-9_.]+/[a-zA-Z0-9_.]+', output)
        if match:
            return match.group().split('/')[0]
        return ''
    
    def _app_current_uiautomator2(self) -> str:
        """uiautomator2方式获取当前应用包名"""
        return self.u2.app_current()['package']
    
    def _app_current_adb(self) -> str:
        """ADB方式获取当前应用包名"""
        output = self.adb.shell(['dumpsys', 'window', 'windows', '|', 'grep', 'mCurrentFocus'])
        match = re.search(r'[a-zA-Z0-9_.]+/[a-zA-Z0-9_.]+', output)
        if match:
            return match.group().split('/')[0]
        return ''
    
    def app_is_running(self) -> bool:
        """
        检查目标应用是否正在运行。
        
        Returns:
            bool: 如果目标应用正在运行则返回True，否则返回False
        """
        if self._package is None:
            raise Exception("未设置目标应用包名")
            
        package = self.app_current()
        logger.attr('Package_name', package)
        return package == self._package
    
    def app_start(self) -> None:
        """
        启动目标应用程序。
        
        功能说明：
        - 根据设备类型选择合适的启动方法
        - 支持WSA、uiautomator2和原生ADB三种启动方式
        - 使用不同的启动命令确保应用正确启动
        
        启动方式：
        1. WSA方式：使用am start命令启动MainActivity
        2. uiautomator2方式：使用u2.app_start方法启动
        3. ADB方式：使用monkey命令启动应用
        
        异常说明：
        - 当未设置目标应用包名时抛出异常
        - 当设备未连接时可能抛出异常
        - 当应用未安装时可能抛出异常
        
        使用示例：
            device_manager.package = "com.example.app"
            device_manager.app_start()
        """
        if not self._package:
            raise Exception("未设置目标应用包名")
            
        logger.info(f'App start: {self._package}')
        
        # 根据设备类型选择启动方式
        if DeviceUtils.is_wsa(self._serial):
            self.adb.shell(['am', 'start', '-n', f'{self._package}/.MainActivity'])  # WSA方式启动
        elif DeviceUtils.is_uiautomator2_supported(self._serial):
            self.u2.app_start(self._package)  # uiautomator2方式启动
        else:
            self.adb.shell(['monkey', '-p', self._package, '-c', 'android.intent.category.LAUNCHER', '1'])  # ADB方式启动
    
    def app_stop(self) -> None:
        """
        停止目标应用程序。
        
        功能说明：
        - 根据设备类型选择合适的停止方法
        - 支持uiautomator2和原生ADB两种停止方式
        - 使用force-stop命令确保应用完全停止
        
        异常说明：
        - 当未设置目标应用包名时抛出异常
        - 当设备未连接时可能抛出异常
        
        使用示例：
            device_manager.package = "com.example.app"
            device_manager.app_stop()
        """
        if not self._package:
            raise Exception("未设置目标应用包名")
            
        logger.info(f'App stop: {self._package}')
        if DeviceUtils.is_uiautomator2_supported(self._serial):
            self.u2.app_stop(self._package)  # 使用uiautomator2的app_stop方法停止应用
        else:
            self.adb.shell(['am', 'force-stop', self._package])  # 使用ADB的force-stop命令停止应用
    
    def hierarchy_timer_set(self, interval: Optional[float] = None) -> None:
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
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        self._hierarchy_interval.wait()
        self._hierarchy_interval.reset()

        # 使用uiautomator2获取界面层级
        self._hierarchy = self.u2.dump_hierarchy()
        return self._hierarchy
    
    def xpath_to_button(self, xpath: str) -> Optional[HierarchyButton]:
        """
        将xpath路径转换为可点击的按钮对象。
        
        Args:
            xpath (str): 要查找元素的xpath路径

        Returns:
            Optional[HierarchyButton]: 具有类似Button对象方法和属性的按钮对象
                                     如果未找到元素或找到多个元素则返回None
        """
        if self._hierarchy is None:
            self.dump_hierarchy()
        return HierarchyButton(self._hierarchy, xpath)

    def screenshot(self):
        """
        获取屏幕截图。
        
        Returns:
            np.ndarray: 屏幕截图数据
            
        Raises:
            Exception: 未连接设备时抛出异常
            ImageTruncated: 当图像数据无效时抛出
        """
        if self._serial is None:
            raise Exception("未连接设备")
            
        data = self.adb.shell(['screencap', '-p'], stream=True)
        return ImageUtils.load_screencap(data)


# 创建全局设备管理器实例
device_manager = DeviceManager() 