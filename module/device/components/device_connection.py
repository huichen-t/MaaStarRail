"""
设备连接组件模块。
提供设备连接相关的功能，包括：
- ADB连接管理
- 设备检测
- 设备信息获取
"""

from typing import Optional, List, Dict, Any
from adbutils.errors import AdbError

from module.device.method.utils import handle_adb_error, handle_unknown_host_service
from module.exception import RequestHumanTakeover
from module.base.logger import logger


class DeviceConnectionError(Exception):
    """设备连接相关错误的异常类"""
    pass


class DeviceConnection:
    """
    设备连接组件类。
    提供设备连接相关的功能。
    """
    def __init__(self, adb: Any, config: Dict[str, Any]):
        self.adb = adb
        self.config = config
        self._device_id = None
        self._cpu_abi = None
        self._sdk_ver = None

    @property
    def device_id(self) -> str:
        """
        获取设备ID。
        
        Returns:
            str: 设备ID
        """
        if not self._device_id:
            self._device_id = self.adb.device_id()
        return self._device_id

    @property
    def cpu_abi(self) -> str:
        """
        获取设备CPU架构。
        
        Returns:
            str: CPU架构
        """
        if not self._cpu_abi:
            self._cpu_abi = self.adb.shell(['getprop', 'ro.product.cpu.abi']).strip()
        return self._cpu_abi

    @property
    def sdk_ver(self) -> int:
        """
        获取设备Android SDK版本。
        
        Returns:
            int: SDK版本
        """
        if not self._sdk_ver:
            self._sdk_ver = int(self.adb.shell(['getprop', 'ro.build.version.sdk']).strip())
        return self._sdk_ver

    def connect(self, device_id: str) -> bool:
        """
        连接到指定设备。
        
        Args:
            device_id: 设备ID
            
        Returns:
            bool: 连接是否成功
            
        Raises:
            DeviceConnectionError: 当连接失败时抛出
        """
        try:
            self.adb.connect(device_id)
            self._device_id = device_id
            return True
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to connect to device {device_id}: {e}')
                raise DeviceConnectionError(f'Failed to connect to device {device_id}: {e}')
            return False

    def disconnect(self) -> None:
        """
        断开设备连接。
        
        Raises:
            DeviceConnectionError: 当断开连接失败时抛出
        """
        try:
            self.adb.disconnect()
            self._device_id = None
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to disconnect device: {e}')
                raise DeviceConnectionError(f'Failed to disconnect device: {e}')

    def reconnect(self) -> None:
        """
        重新连接设备。
        
        Raises:
            DeviceConnectionError: 当重连失败时抛出
        """
        try:
            self.disconnect()
            self.connect(self.device_id)
        except DeviceConnectionError as e:
            logger.error(f'Failed to reconnect device: {e}')
            raise DeviceConnectionError(f'Failed to reconnect device: {e}')

    def start_server(self) -> None:
        """
        启动ADB服务器。
        
        Raises:
            DeviceConnectionError: 当启动服务器失败时抛出
        """
        try:
            self.adb.start_server()
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to start ADB server: {e}')
                raise DeviceConnectionError(f'Failed to start ADB server: {e}')

    def list_device(self) -> List[str]:
        """
        获取已连接的设备列表。
        
        Returns:
            List[str]: 设备ID列表
            
        Raises:
            DeviceConnectionError: 当获取设备列表失败时抛出
        """
        try:
            return self.adb.device_list()
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to list devices: {e}')
                raise DeviceConnectionError(f'Failed to list devices: {e}')
            return []

    def get_orientation(self) -> int:
        """
        获取设备方向。
        
        Returns:
            int: 设备方向（0: 竖屏, 1: 横屏）
            
        Raises:
            DeviceConnectionError: 当获取设备方向失败时抛出
        """
        try:
            result = self.adb.shell(['dumpsys', 'input']).strip()
            if 'SurfaceOrientation: 0' in result:
                return 0
            elif 'SurfaceOrientation: 1' in result:
                return 1
            else:
                return 0
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to get device orientation: {e}')
                raise DeviceConnectionError(f'Failed to get device orientation: {e}')
            return 0 