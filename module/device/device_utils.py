"""
设备工具模块。
提供设备连接、识别和管理的工具函数。

主要功能：
1. 设备序列号处理
   - 标准化序列号格式
   - 验证序列号有效性
   - 提取端口信息

2. 设备类型识别
   - 模拟器类型判断
   - 连接方式判断
   - 设备特性判断

3. 设备连接管理
   - ADB连接
   - HTTP连接
   - 特殊模拟器连接
"""

import os
import re
from typing import Optional, Tuple, Dict, Any

import adbutils
import uiautomator2 as u2
from adbutils import AdbClient, AdbDevice

from module.base.decorator import cached_property
from module.config.config_manager import config_manager
from module.base.logger import logger


class DeviceUtils:
    """
    设备工具类。
    提供设备连接、识别和管理的工具函数。
    """
    
    # 常见模拟器端口范围
    EMULATOR_PORTS = {
        'mumu': (16384, 17408),      # MuMu12系列
        'mumu_old': (7555, 7555),    # 旧版MuMu
        'nox': (62001, 63025),       # 夜神模拟器
        'ldplayer': (5555, 5587),    # 雷电模拟器
        'vmos': (5667, 5699),        # VMOS虚拟机
        'chinac': (301, 309),        # 中国云手机
    }
    
    # 支持的adb可执行文件路径列表，按优先级排序
    ADB_BINARY_PATHS = [
        './bin/adb/adb.exe',  # 项目内置ADB
        './toolkit/Lib/site-packages/adbutils/binaries/adb.exe',  # 工具包ADB
        '/usr/bin/adb'  # 系统ADB
    ]

    def __init__(self, config_name: str = None):
        """
        初始化设备工具类。
        
        Args:
            config_name (str, optional): 配置名称，如果为None则使用默认配置
        """
        # 使用配置管理器获取平台配置
        self.config = config_manager.platform
        
        # 如果提供了配置名称，则加载指定配置
        if config_name is not None:
            self.config.load(config_name)
            
        # 初始化设备序列号
        self.serial = str(self.config.get_value('device.serial'))
        self._init_connection()

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

    @classmethod
    def get_device_serial(cls, input_serial: str) -> str:
        """
        获取标准化的设备序列号。
        
        Args:
            input_serial (str): 输入的设备序列号
            
        Returns:
            str: 标准化后的设备序列号
        """
        return cls.revise_serial(input_serial)

    @classmethod
    def is_valid_serial(cls, serial: str) -> bool:
        """
        检查序列号是否有效。
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 序列号是否有效
        """
        try:
            revised = cls.revise_serial(serial)
            return bool(revised)
        except:
            return False

    @staticmethod
    def revise_serial(serial: str) -> str:
        """
        修正和标准化设备序列号。
        
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

    @classmethod
    def get_common_ports(cls) -> Dict[str, Tuple[int, int]]:
        """
        获取常见模拟器的端口范围。
        
        Returns:
            Dict[str, Tuple[int, int]]: 模拟器名称和端口范围的映射
        """
        return cls.EMULATOR_PORTS

    @cached_property
    def port(self) -> int:
        """
        获取设备端口号。
        
        Returns:
            int: 端口号，获取失败返回0
        """
        try:
            return int(self.serial.split(':')[1])
        except (IndexError, ValueError):
            return 0

    @cached_property
    def is_mumu_family(self) -> bool:
        """判断是否为MuMu系列模拟器"""
        return (self.serial == '127.0.0.1:7555' or 
                self.EMULATOR_PORTS['mumu'][0] <= self.port <= self.EMULATOR_PORTS['mumu'][1])

    @cached_property
    def is_nox_family(self) -> bool:
        """判断是否为夜神模拟器"""
        return self.EMULATOR_PORTS['nox'][0] <= self.port <= self.EMULATOR_PORTS['nox'][1]

    @cached_property
    def is_ldplayer_family(self) -> bool:
        """判断是否为雷电模拟器"""
        return self.EMULATOR_PORTS['ldplayer'][0] <= self.port <= self.EMULATOR_PORTS['ldplayer'][1]

    @cached_property
    def is_vmos(self) -> bool:
        """判断是否为VMOS虚拟机"""
        return self.EMULATOR_PORTS['vmos'][0] <= self.port <= self.EMULATOR_PORTS['vmos'][1]

    @cached_property
    def is_emulator(self) -> bool:
        """判断是否为通用模拟器"""
        return self.serial.startswith('emulator-') or self.serial.startswith('127.0.0.1:')

    @cached_property
    def is_network_device(self) -> bool:
        """判断是否为网络设备"""
        return bool(re.match(r'\d+\.\d+\.\d+\.\d+:\d+', self.serial))

    @cached_property
    def is_local_network_device(self) -> bool:
        """判断是否为本地局域网设备"""
        return bool(re.match(r'192\.168\.\d+\.\d+:\d+', self.serial))

    @cached_property
    def is_over_http(self) -> bool:
        """判断是否为HTTP连接设备"""
        return bool(re.match(r"^https?://", self.serial))

    @cached_property
    def is_chinac_phone_cloud(self) -> bool:
        """判断是否为中国云手机"""
        return self.EMULATOR_PORTS['chinac'][0] <= self.port <= self.EMULATOR_PORTS['chinac'][1]

    @cached_property
    def adb_binary(self) -> str:
        """
        获取adb可执行文件路径。
        
        Returns:
            str: adb可执行文件路径
        """
        # 从配置中获取adb路径
        file = self.config.get_value('device.adb_path')
        if file and os.path.exists(file):
            return os.path.abspath(file)

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
        """
        return AdbDevice(self.adb_client, self.serial)

    @cached_property
    def u2(self) -> u2.Device:
        """
        获取uiautomator2设备对象。
        
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

    def get_device_info(self) -> Dict[str, Any]:
        """
        获取设备信息。
        
        Returns:
            Dict[str, Any]: 设备信息字典
        """
        return {
            'serial': self.serial,
            'port': self.port,
            'is_emulator': self.is_emulator,
            'is_network_device': self.is_network_device,
            'is_over_http': self.is_over_http,
            'device_type': self._get_device_type(),
            'adb_path': self.adb_binary
        }

    def _get_device_type(self) -> str:
        """
        获取设备类型。
        
        Returns:
            str: 设备类型名称
        """
        if self.is_mumu_family:
            return 'MuMu'
        elif self.is_nox_family:
            return 'Nox'
        elif self.is_ldplayer_family:
            return 'LDPlayer'
        elif self.is_vmos:
            return 'VMOS'
        elif self.is_chinac_phone_cloud:
            return 'ChinaC'
        elif self.is_emulator:
            return 'Emulator'
        elif self.is_network_device:
            return 'Network'
        else:
            return 'Unknown' 