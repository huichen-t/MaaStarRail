"""
设备连接属性模块。
用于管理设备连接的各种属性和方法，包括：
- ADB连接管理
- 设备序列号处理
- 模拟器类型识别
- 设备连接方式判断
"""

import os
import re

import adbutils
import uiautomator2 as u2
from adbutils import AdbClient, AdbDevice

from module.base.decorator import cached_property
from module.config.config_manager import config_manager  # 更新导入
from module.device.method.utils import get_serial_pair
from module.exception import RequestHumanTakeover
from module.base.logger import logger


class ConnectionAttr:
    """
    设备连接属性类。
    用于管理设备连接的各种属性和方法，包括ADB连接、设备识别、模拟器判断等。
    
    主要功能：
    1. 设备连接管理
       - ADB客户端初始化
       - 设备序列号处理
       - 连接方式判断（USB/HTTP）
    
    2. 设备类型识别
       - 模拟器类型判断（MuMu/BlueStacks/夜神等）
       - 网络设备判断
       - WSA设备判断
    
    3. 设备配置管理
       - ADB路径配置
       - 设备参数设置
       - 连接方式配置
    """
    
    def __init__(self, config_name: str = None):
        """
        初始化设备连接属性。
        
        Args:
            config_name (str, optional): 配置名称，如果为None则使用默认配置
        """
        logger.hr('Device', level=1)
        
        # 使用配置管理器获取平台配置
        self.config = config_manager.platform
        
        # 如果提供了配置名称，则加载指定配置
        if config_name is not None:
            self.config.load(config_name)

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

        # 处理设备序列号
        self.serial = str(self.config.get_value('device.serial'))
        self.serial_check()
        self.config.set_value('device.over_http', self.is_over_http)

    @staticmethod
    def revise_serial(serial):
        """
        修正和标准化设备序列号。
        处理各种格式的序列号，统一转换为标准格式。
        
        支持的格式：
        - IP:端口 (127.0.0.1:5555)
        - 端口号 (16384)
        - 模拟器名称 (夜神模拟器)
        - 特殊格式 (bluestacks4-hyperv)
        
        Args:
            serial (str): 原始序列号
            
        Returns:
            str: 修正后的标准序列号
        """
        serial = serial.replace(' ', '')
        # 处理中文标点
        serial = serial.replace('。', '.').replace('，', '.').replace(',', '.').replace('：', ':')
        # 处理IP地址格式
        serial = serial.replace('127.0.0.1.', '127.0.0.1:')
        # 处理纯端口号
        try:
            port = int(serial)
            if 1000 < port < 65536:
                serial = f'127.0.0.1:{port}'
        except ValueError:
            pass
        # 处理模拟器名称
        if '模拟' in serial:
            res = re.search(r'(127\.\d+\.\d+\.\d+:\d+)', serial)
            if res:
                serial = res.group(1)
        # 处理特殊IP格式
        serial = serial.replace('12127.0.0.1', '127.0.0.1')
        # 处理auto前缀
        serial = serial.replace('auto127.0.0.1', '127.0.0.1').replace('autoemulator', 'emulator')
        return str(serial)

    def serial_check(self):
        """
        检查并修正设备序列号。
        处理特殊模拟器和WSA等情况，确保序列号正确。
        """
        # 修正序列号格式
        new = self.revise_serial(self.serial)
        if new != self.serial:
            logger.warning(f'Serial "{self.config.get_value("device.serial")}" is revised to "{new}"')
            self.config.set_value('device.serial', new)
            self.serial = new
            
        # 处理BlueStacks Hyper-V
        if self.is_bluestacks4_hyperv:
            self.serial = self.find_bluestacks4_hyperv(self.serial)
        if self.is_bluestacks5_hyperv:
            self.serial = self.find_bluestacks5_hyperv(self.serial)
            
        # 处理WSA
        if "127.0.0.1:58526" in self.serial:
            logger.warning('Serial 127.0.0.1:58526 seems to be WSA, '
                           'please use "wsa-0" or others instead')
            raise RequestHumanTakeover
        if self.is_wsa:
            self.serial = '127.0.0.1:58526'
            # WSA必须使用uiautomator2
            if self.config.get_value('device.screenshot_method') != 'uiautomator2' \
                    or self.config.get_value('device.control_method') != 'uiautomator2':
                self.config.update({
                    'device.screenshot_method': 'uiautomator2',
                    'device.control_method': 'uiautomator2'
                })
                    
        # 处理HTTP连接
        if self.is_over_http:
            if self.config.get_value('device.screenshot_method') not in ["ADB", "uiautomator2", "aScreenCap"] \
                    or self.config.get_value('device.control_method') not in ["ADB", "uiautomator2", "minitouch"]:
                logger.warning(
                    f'When connecting to a device over http: {self.serial} '
                    f'ScreenshotMethod can only use ["ADB", "uiautomator2", "aScreenCap"], '
                    f'ControlMethod can only use ["ADB", "uiautomator2", "minitouch"]'
                )
                raise RequestHumanTakeover

    @cached_property
    def is_bluestacks4_hyperv(self):
        """判断是否为BlueStacks4 Hyper-V模拟器"""
        return "bluestacks4-hyperv" in self.serial

    @cached_property
    def is_bluestacks5_hyperv(self):
        """判断是否为BlueStacks5 Hyper-V模拟器"""
        return "bluestacks5-hyperv" in self.serial

    @cached_property
    def is_bluestacks_hyperv(self):
        """判断是否为BlueStacks Hyper-V系列模拟器"""
        return self.is_bluestacks4_hyperv or self.is_bluestacks5_hyperv

    @cached_property
    def is_wsa(self):
        """判断是否为Windows子系统安卓(WSA)"""
        return bool(re.match(r'^wsa', self.serial))

    @cached_property
    def port(self) -> int:
        """
        获取设备端口号。
        
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
        """判断是否为MuMu12系列模拟器（端口16384-17408）"""
        return 16384 <= self.port <= 17408

    @cached_property
    def is_mumu_family(self):
        """判断是否为MuMu系列模拟器"""
        return self.serial == '127.0.0.1:7555' or self.is_mumu12_family

    @cached_property
    def is_ldplayer_bluestacks_family(self):
        """判断是否为雷电模拟器或BlueStacks系列（端口5555-5587或emulator-开头）"""
        return self.serial.startswith('emulator-') or 5555 <= self.port <= 5587

    @cached_property
    def is_nox_family(self):
        """判断是否为夜神模拟器（端口62001-63025）"""
        return 62001 <= self.port <= 63025

    @cached_property
    def is_vmos(self):
        """判断是否为VMOS虚拟机（端口5667-5699）"""
        return 5667 <= self.port <= 5699

    @cached_property
    def is_emulator(self):
        """判断是否为通用模拟器（emulator-或127.0.0.1:开头）"""
        return self.serial.startswith('emulator-') or self.serial.startswith('127.0.0.1:')

    @cached_property
    def is_network_device(self):
        """判断是否为网络设备（IP:端口格式）"""
        return bool(re.match(r'\d+\.\d+\.\d+\.\d+:\d+', self.serial))

    @cached_property
    def is_local_network_device(self):
        """判断是否为本地局域网设备（192.168.x.x:端口）"""
        return bool(re.match(r'192\.168\.\d+\.\d+:\d+', self.serial))

    @cached_property
    def is_over_http(self):
        """判断是否为HTTP连接设备（http://或https://开头）"""
        return bool(re.match(r"^https?://", self.serial))

    @cached_property
    def is_chinac_phone_cloud(self):
        """判断是否为中国云手机（端口301-309）"""
        return bool(re.search(r":30[0-9]$", self.serial))

    @staticmethod
    def find_bluestacks4_hyperv(serial):
        """
        查找BlueStacks4 Hyper-V Beta的动态端口。
        通过注册表获取实际的ADB端口。
        
        Args:
            serial (str): 形如'bluestacks4-hyperv'或'bluestacks4-hyperv-2'等多开实例名
            
        Returns:
            str: 127.0.0.1:{port}
            
        Raises:
            RequestHumanTakeover: 当无法找到注册表或端口时抛出
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
        通过配置文件获取实际的ADB端口。
        
        Args:
            serial (str): 形如'bluestacks5-hyperv'或'bluestacks5-hyperv-1'等多开实例名
            
        Returns:
            str: 127.0.0.1:{port}
            
        Raises:
            RequestHumanTakeover: 当无法找到配置文件或端口时抛出
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
        按以下优先级查找：
        1. 配置文件中指定的路径
        2. 常用路径列表
        3. python环境中的adb
        4. 系统PATH中的adb
        
        Returns:
            str: adb可执行文件路径
        """
        # 从配置中获取adb路径
        file = self.config.get_value('device.adb_path')
        if file and os.path.exists(file):
            return os.path.abspath(file)

        # 检查常用路径
        for file in self.adb_binary_list:
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
        根据连接方式选择不同的连接方法：
        - HTTP连接：直接使用URL连接
        - USB连接：使用USB连接
        - 其他：使用默认连接方式
        
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
