import os
import re

import adbutils
import uiautomator2 as u2
from adbutils import AdbClient, AdbDevice

from module.base.decorator import cached_property
from module.config_src.config import AzurLaneConfig
from module.device.method.utils import get_serial_pair
from module.exception import RequestHumanTakeover
from module.logger import logger


class ConnectionAttr:
    config: AzurLaneConfig
    serial: str

    # 支持的adb可执行文件路径列表
    adb_binary_list = [
        './bin/adb/adb.exe',
        './toolkit/Lib/site-packages/adbutils/binaries/adb.exe',
        '/usr/bin/adb'
    ]

    def __init__(self, config):
        """
        初始化ConnectionAttr对象。
        
        Args:
            config (AzurLaneConfig, str): 用户配置对象或配置文件名。
        """
        logger.hr('Device', level=1)
        if isinstance(config, str):
            self.config = AzurLaneConfig(config, task=None)
        else:
            self.config = config

        # 初始化adb client
        logger.attr('AdbBinary', self.adb_binary)
        # 设置adbutils使用自定义adb路径
        adbutils.adb_path = lambda: self.adb_binary
        # 移除全局代理，避免uiautomator2走代理
        for k in list(os.environ.keys()):
            if k.lower().endswith('_proxy'):
                del os.environ[k]
        # 缓存adb_client
        _ = self.adb_client

        # 解析自定义序列号
        self.serial = str(self.config.Emulator_Serial)
        self.serial_check()
        self.config.DEVICE_OVER_HTTP = self.is_over_http

    @staticmethod
    def revise_serial(serial):
        """
        修正和标准化设备序列号字符串。
        处理常见的格式错误和中文符号。
        
        Args:
            serial (str): 原始序列号
        Returns:
            str: 修正后的序列号
        """
        serial = serial.replace(' ', '')
        # 127。0。0。1：5555
        serial = serial.replace('。', '.').replace('，', '.').replace(',', '.').replace('：', ':')
        # 127.0.0.1.5555
        serial = serial.replace('127.0.0.1.', '127.0.0.1:')
        # 16384
        try:
            port = int(serial)
            if 1000 < port < 65536:
                serial = f'127.0.0.1:{port}'
        except ValueError:
            pass
        # 夜神模拟器 127.0.0.1:62001
        # MuMu模拟器12127.0.0.1:16384
        if '模拟' in serial:
            res = re.search(r'(127\.\d+\.\d+\.\d+:\d+)', serial)
            if res:
                serial = res.group(1)
        # 12127.0.0.1:16384
        serial = serial.replace('12127.0.0.1', '127.0.0.1')
        # auto127.0.0.1:16384
        serial = serial.replace('auto127.0.0.1', '127.0.0.1').replace('autoemulator', 'emulator')
        return str(serial)

    def serial_check(self):
        """
        检查并修正设备序列号，处理特殊模拟器和WSA等情况。
        """
        # 容错处理
        new = self.revise_serial(self.serial)
        if new != self.serial:
            logger.warning(f'Serial "{self.config.Emulator_Serial}" is revised to "{new}"')
            self.config.Emulator_Serial = new
            self.serial = new
        if self.is_bluestacks4_hyperv:
            self.serial = self.find_bluestacks4_hyperv(self.serial)
        if self.is_bluestacks5_hyperv:
            self.serial = self.find_bluestacks5_hyperv(self.serial)
        if "127.0.0.1:58526" in self.serial:
            logger.warning('Serial 127.0.0.1:58526 seems to be WSA, '
                           'please use "wsa-0" or others instead')
            raise RequestHumanTakeover
        if self.is_wsa:
            self.serial = '127.0.0.1:58526'
            if self.config.Emulator_ScreenshotMethod != 'uiautomator2' \
                    or self.config.Emulator_ControlMethod != 'uiautomator2':
                with self.config.multi_set():
                    self.config.Emulator_ScreenshotMethod = 'uiautomator2'
                    self.config.Emulator_ControlMethod = 'uiautomator2'
        if self.is_over_http:
            if self.config.Emulator_ScreenshotMethod not in ["ADB", "uiautomator2", "aScreenCap"] \
                    or self.config.Emulator_ControlMethod not in ["ADB", "uiautomator2", "minitouch"]:
                logger.warning(
                    f'When connecting to a device over http: {self.serial} '
                    f'ScreenshotMethod can only use ["ADB", "uiautomator2", "aScreenCap"], '
                    f'ControlMethod can only use ["ADB", "uiautomator2", "minitouch"]'
                )
                raise RequestHumanTakeover

    @cached_property
    def is_bluestacks4_hyperv(self):
        """
        判断当前序列号是否为BlueStacks4 Hyper-V。
        Returns:
            bool: 是否为BlueStacks4 Hyper-V
        """
        return "bluestacks4-hyperv" in self.serial

    @cached_property
    def is_bluestacks5_hyperv(self):
        """
        判断当前序列号是否为BlueStacks5 Hyper-V。
        Returns:
            bool: 是否为BlueStacks5 Hyper-V
        """
        return "bluestacks5-hyperv" in self.serial

    @cached_property
    def is_bluestacks_hyperv(self):
        """
        判断当前序列号是否为BlueStacks Hyper-V系列。
        Returns:
            bool: 是否为BlueStacks Hyper-V系列
        """
        return self.is_bluestacks4_hyperv or self.is_bluestacks5_hyperv

    @cached_property
    def is_wsa(self):
        """
        判断当前序列号是否为WSA（Windows子系统安卓）。
        Returns:
            bool: 是否为WSA
        """
        return bool(re.match(r'^wsa', self.serial))

    @cached_property
    def port(self) -> int:
        """
        获取当前序列号的端口号。
        Returns:
            int: 端口号，获取失败返回0
        """
        port_serial, _ = get_serial_pair(self.serial)
        if port_serial is None:
            port_serial = self.serial
        try:
            return int(port_serial.split(':')[1])
        except (IndexError, ValueError):
            return 0

    @cached_property
    def is_mumu12_family(self):
        """
        判断是否为MuMu12系列模拟器（端口16384-17408）。
        Returns:
            bool: 是否为MuMu12系列
        """
        return 16384 <= self.port <= 17408

    @cached_property
    def is_mumu_family(self):
        """
        判断是否为MuMu系列模拟器。
        Returns:
            bool: 是否为MuMu系列
        """
        return self.serial == '127.0.0.1:7555' or self.is_mumu12_family

    @cached_property
    def is_ldplayer_bluestacks_family(self):
        """
        判断是否为雷电模拟器或BlueStacks系列（端口5555-5587或emulator-开头）。
        Returns:
            bool: 是否为LDPlayer或BlueStacks系列
        """
        return self.serial.startswith('emulator-') or 5555 <= self.port <= 5587

    @cached_property
    def is_nox_family(self):
        """
        判断是否为夜神模拟器（端口62001-63025）。
        Returns:
            bool: 是否为夜神模拟器
        """
        return 62001 <= self.port <= 63025

    @cached_property
    def is_vmos(self):
        """
        判断是否为VMOS虚拟机（端口5667-5699）。
        Returns:
            bool: 是否为VMOS
        """
        return 5667 <= self.port <= 5699

    @cached_property
    def is_emulator(self):
        """
        判断是否为通用模拟器（emulator-或127.0.0.1:开头）。
        Returns:
            bool: 是否为模拟器
        """
        return self.serial.startswith('emulator-') or self.serial.startswith('127.0.0.1:')

    @cached_property
    def is_network_device(self):
        """
        判断是否为网络设备（IP:端口格式）。
        Returns:
            bool: 是否为网络设备
        """
        return bool(re.match(r'\d+\.\d+\.\d+\.\d+:\d+', self.serial))

    @cached_property
    def is_local_network_device(self):
        """
        判断是否为本地局域网设备（192.168.x.x:端口）。
        Returns:
            bool: 是否为本地局域网设备
        """
        return bool(re.match(r'192\.168\.\d+\.\d+:\d+', self.serial))

    @cached_property
    def is_over_http(self):
        """
        判断是否为HTTP连接设备。
        Returns:
            bool: 是否为HTTP连接
        """
        return bool(re.match(r"^https?://", self.serial))

    @cached_property
    def is_chinac_phone_cloud(self):
        """
        判断是否为中国云手机（端口301-309）。
        Returns:
            bool: 是否为中国云手机
        """
        return bool(re.search(r":30[0-9]$", self.serial))

    @staticmethod
    def find_bluestacks4_hyperv(serial):
        """
        查找BlueStacks4 Hyper-V Beta的动态端口。
        
        Args:
            serial (str): 形如'bluestacks4-hyperv'或'bluestacks4-hyperv-2'等多开实例名
        Returns:
            str: 127.0.0.1:{port}
        """
        from winreg import HKEY_LOCAL_MACHINE, OpenKey, QueryValueEx

        logger.info("Use BlueStacks4 Hyper-V Beta")
        logger.info("Reading Realtime adb port")

        if serial == "bluestacks4-hyperv":
            folder_name = "Android"
        else:
            folder_name = f"Android_{serial[19:]}"

        try:
            with OpenKey(HKEY_LOCAL_MACHINE,
                         rf"SOFTWARE\BlueStacks_bgp64_hyperv\Guests\{folder_name}\Config") as key:
                port = QueryValueEx(key, "BstAdbPort")[0]
        except FileNotFoundError:
            logger.error(
                rf'Unable to find registry HKEY_LOCAL_MACHINE\SOFTWARE\BlueStacks_bgp64_hyperv\Guests\{folder_name}\Config')
            logger.error('Please confirm that your are using BlueStack 4 hyper-v and not regular BlueStacks 4')
            logger.error(r'Please check if there is any other emulator instances under '
                         r'registry HKEY_LOCAL_MACHINE\SOFTWARE\BlueStacks_bgp64_hyperv\Guests')
            raise RequestHumanTakeover
        logger.info(f"New adb port: {port}")
        return f"127.0.0.1:{port}"

    @staticmethod
    def find_bluestacks5_hyperv(serial):
        """
        查找BlueStacks5 Hyper-V的动态端口。
        
        Args:
            serial (str): 形如'bluestacks5-hyperv'或'bluestacks5-hyperv-1'等多开实例名
        Returns:
            str: 127.0.0.1:{port}
        """
        from winreg import HKEY_LOCAL_MACHINE, OpenKey, QueryValueEx

        logger.info("Use BlueStacks5 Hyper-V")
        logger.info("Reading Realtime adb port")

        if serial == "bluestacks5-hyperv":
            parameter_name = r"bst\.instance\.(Nougat64|Pie64|Rvc64)\.status\.adb_port"
        else:
            parameter_name = rf"bst\.instance\.(Nougat64|Pie64|Rvc64)_{serial[19:]}\.status.adb_port"

        try:
            with OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\BlueStacks_nxt") as key:
                directory = QueryValueEx(key, 'UserDefinedDir')[0]
        except FileNotFoundError:
            try:
                with OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\BlueStacks_nxt_cn") as key:
                    directory = QueryValueEx(key, 'UserDefinedDir')[0]
            except FileNotFoundError:
                logger.error('Unable to find registry HKEY_LOCAL_MACHINE\SOFTWARE\BlueStacks_nxt '
                             'or HKEY_LOCAL_MACHINE\SOFTWARE\BlueStacks_nxt_cn')
                logger.error('Please confirm that you are using BlueStacks 5 hyper-v and not regular BlueStacks 5')
                raise RequestHumanTakeover
        logger.info(f"Configuration file directory: {directory}")

        with open(os.path.join(directory, 'bluestacks.conf'), encoding='utf-8') as f:
            content = f.read()
        port = re.search(rf'{parameter_name}="(\d+)"', content)
        if port is None:
            logger.warning(f"Did not match the result: {serial}.")
            raise RequestHumanTakeover
        port = port.group(2)
        logger.info(f"Match to dynamic port: {port}")
        return f"127.0.0.1:{port}"

    @cached_property
    def adb_binary(self):
        """
        获取adb可执行文件路径。
        优先级：deploy.yaml配置 > 常用路径 > python环境 > 系统PATH
        Returns:
            str: adb可执行文件路径
        """
        from module.webui.setting import State
        file = State.deploy_config.AdbExecutable
        file = file.replace('\\', '/')
        if os.path.exists(file):
            return os.path.abspath(file)

        for file in self.adb_binary_list:
            if os.path.exists(file):
                return os.path.abspath(file)

        import sys
        file = os.path.join(sys.executable, '../Lib/site-packages/adbutils/binaries/adb.exe')
        file = os.path.abspath(file).replace('\\', '/')
        if os.path.exists(file):
            return file

        file = 'adb'
        return file

    @cached_property
    def adb_client(self) -> AdbClient:
        """
        获取AdbClient对象。
        优先使用环境变量ANDROID_ADB_SERVER_PORT指定的端口。
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
        """
        return AdbDevice(self.adb_client, self.serial)

    @cached_property
    def u2(self) -> u2.Device:
        """
        获取uiautomator2设备对象。
        根据连接方式选择不同的连接方法。
        Returns:
            u2.Device: uiautomator2设备对象
        """
        if self.is_over_http:
            device = u2.connect(self.serial)
        else:
            if self.serial.startswith('emulator-') or self.serial.startswith('127.0.0.1:'):
                device = u2.connect_usb(self.serial)
            else:
                device = u2.connect(self.serial)

        # 设置命令超时时间，防止连接断开
        device.set_new_command_timeout(604800)

        logger.attr('u2.Device', f'Device(atx_agent_url={device._get_atx_agent_url()})')
        return device
