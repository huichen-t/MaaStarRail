"""
设备工具模块。
提供设备序列号处理、类型识别等静态工具函数。

主要功能：
1. 设备序列号处理
   - 标准化序列号格式
   - 验证序列号有效性
   - 提取端口信息

2. 设备类型识别
   - 模拟器类型判断
   - 连接方式判断
   - 设备特性判断
"""

import re
from typing import Dict, Tuple


class DeviceUtils:
    """
    设备工具类。
    提供设备序列号处理、类型识别等静态工具函数。
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

    @classmethod
    def get_common_ports(cls) -> Dict[str, Tuple[int, int]]:
        """
        获取常见模拟器的端口范围。
        
        Returns:
            Dict[str, Tuple[int, int]]: 模拟器名称和端口范围的映射
        """
        return cls.EMULATOR_PORTS

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
    def extract_port(serial: str) -> int:
        """
        获取设备端口号。
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            int: 端口号，获取失败返回0
        """
        try:
            return int(serial.split(':')[1])
        except (IndexError, ValueError):
            return 0

    @classmethod
    def is_mumu_family(cls, serial: str) -> bool:
        """
        判断是否为MuMu系列模拟器
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 是否为MuMu系列模拟器
        """
        port = cls.extract_port(serial)
        return (serial == '127.0.0.1:7555' or 
                cls.EMULATOR_PORTS['mumu'][0] <= port <= cls.EMULATOR_PORTS['mumu'][1])

    @classmethod
    def is_nox_family(cls, serial: str) -> bool:
        """
        判断是否为夜神模拟器
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 是否为夜神模拟器
        """
        port = cls.extract_port(serial)
        return cls.EMULATOR_PORTS['nox'][0] <= port <= cls.EMULATOR_PORTS['nox'][1]

    @classmethod
    def is_ldplayer_family(cls, serial: str) -> bool:
        """
        判断是否为雷电模拟器
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 是否为雷电模拟器
        """
        port = cls.extract_port(serial)
        return cls.EMULATOR_PORTS['ldplayer'][0] <= port <= cls.EMULATOR_PORTS['ldplayer'][1]

    @classmethod
    def is_vmos(cls, serial: str) -> bool:
        """
        判断是否为VMOS虚拟机
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 是否为VMOS虚拟机
        """
        port = cls.extract_port(serial)
        return cls.EMULATOR_PORTS['vmos'][0] <= port <= cls.EMULATOR_PORTS['vmos'][1]

    @staticmethod
    def is_emulator(serial: str) -> bool:
        """
        判断是否为通用模拟器
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 是否为通用模拟器
        """
        return serial.startswith('emulator-') or serial.startswith('127.0.0.1:')

    @staticmethod
    def is_network_device(serial: str) -> bool:
        """
        判断是否为网络设备
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 是否为网络设备
        """
        return bool(re.match(r'\d+\.\d+\.\d+\.\d+:\d+', serial))

    @staticmethod
    def is_local_network_device(serial: str) -> bool:
        """
        判断是否为本地局域网设备
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 是否为本地局域网设备
        """
        return bool(re.match(r'192\.168\.\d+\.\d+:\d+', serial))

    @staticmethod
    def is_over_http(serial: str) -> bool:
        """
        判断是否为HTTP连接设备
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 是否为HTTP连接设备
        """
        return bool(re.match(r"^https?://", serial))

    @classmethod
    def is_chinac_phone_cloud(cls, serial: str) -> bool:
        """
        判断是否为中国云手机
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            bool: 是否为中国云手机
        """
        port = cls.extract_port(serial)
        return cls.EMULATOR_PORTS['chinac'][0] <= port <= cls.EMULATOR_PORTS['chinac'][1]

    @classmethod
    def get_device_type(cls, serial: str) -> str:
        """
        获取设备类型。
        
        Args:
            serial (str): 设备序列号
            
        Returns:
            str: 设备类型名称
        """
        if cls.is_mumu_family(serial):
            return 'MuMu'
        elif cls.is_nox_family(serial):
            return 'Nox'
        elif cls.is_ldplayer_family(serial):
            return 'LDPlayer'
        elif cls.is_vmos(serial):
            return 'VMOS'
        elif cls.is_chinac_phone_cloud(serial):
            return 'ChinaC'
        elif cls.is_emulator(serial):
            return 'Emulator'
        elif cls.is_network_device(serial):
            return 'Network'
        else:
            return 'Unknown' 