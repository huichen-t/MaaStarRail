"""
命令执行组件模块。
提供命令执行相关的功能，包括：
- ADB命令执行
- Shell命令执行
- 文件传输
"""

from typing import Optional, Union, List, Dict, Any
from adbutils.errors import AdbError

from module.device.method.utils import handle_adb_error, handle_unknown_host_service
from module.exception import RequestHumanTakeover
from module.base.logger import logger


class CommandExecutorError(Exception):
    """命令执行相关错误的异常类"""
    pass


class CommandExecutor:
    """
    命令执行组件类。
    提供命令执行相关的功能。
    """
    def __init__(self, adb: Any, config: Dict[str, Any]):
        self.adb = adb
        self.config = config

    def adb_command(self, cmd: Union[str, List[str]], stream: bool = False) -> Union[str, bytes]:
        """
        执行ADB命令。
        
        Args:
            cmd: 要执行的命令
            stream: 是否以流的形式返回结果
            
        Returns:
            Union[str, bytes]: 命令执行结果
            
        Raises:
            CommandExecutorError: 当命令执行失败时抛出
        """
        try:
            return self.adb.command(cmd, stream=stream)
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to execute ADB command {cmd}: {e}')
                raise CommandExecutorError(f'Failed to execute ADB command {cmd}: {e}')
            return b'' if stream else ''

    def adb_shell(self, cmd: Union[str, List[str]], stream: bool = False) -> Union[str, bytes]:
        """
        执行Shell命令。
        
        Args:
            cmd: 要执行的命令
            stream: 是否以流的形式返回结果
            
        Returns:
            Union[str, bytes]: 命令执行结果
            
        Raises:
            CommandExecutorError: 当命令执行失败时抛出
        """
        try:
            return self.adb.shell(cmd, stream=stream)
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to execute shell command {cmd}: {e}')
                raise CommandExecutorError(f'Failed to execute shell command {cmd}: {e}')
            return b'' if stream else ''

    def adb_shell_nc(self, cmd: Union[str, List[str]]) -> bytes:
        """
        使用netcat执行Shell命令。
        
        Args:
            cmd: 要执行的命令
            
        Returns:
            bytes: 命令执行结果
            
        Raises:
            CommandExecutorError: 当命令执行失败时抛出
        """
        try:
            return self.adb.shell_nc(cmd)
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to execute shell command with netcat {cmd}: {e}')
                raise CommandExecutorError(f'Failed to execute shell command with netcat {cmd}: {e}')
            return b''

    def adb_push(self, local_path: str, remote_path: str) -> None:
        """
        推送文件到设备。
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            
        Raises:
            CommandExecutorError: 当文件推送失败时抛出
        """
        try:
            self.adb.push(local_path, remote_path)
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to push file {local_path} to {remote_path}: {e}')
                raise CommandExecutorError(f'Failed to push file {local_path} to {remote_path}: {e}')

    def adb_pull(self, remote_path: str, local_path: str) -> None:
        """
        从设备拉取文件。
        
        Args:
            remote_path: 远程文件路径
            local_path: 本地文件路径
            
        Raises:
            CommandExecutorError: 当文件拉取失败时抛出
        """
        try:
            self.adb.pull(remote_path, local_path)
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to pull file {remote_path} to {local_path}: {e}')
                raise CommandExecutorError(f'Failed to pull file {remote_path} to {local_path}: {e}')

    def adb_forward(self, local: str, remote: str) -> None:
        """
        设置端口转发。
        
        Args:
            local: 本地端口
            remote: 远程端口
            
        Raises:
            CommandExecutorError: 当端口转发失败时抛出
        """
        try:
            self.adb.forward(local, remote)
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to forward port {local} to {remote}: {e}')
                raise CommandExecutorError(f'Failed to forward port {local} to {remote}: {e}')

    def adb_forward_remove(self, local: str) -> None:
        """
        移除端口转发。
        
        Args:
            local: 本地端口
            
        Raises:
            CommandExecutorError: 当移除端口转发失败时抛出
        """
        try:
            self.adb.forward_remove(local)
        except AdbError as e:
            if handle_adb_error(e):
                logger.error(f'Failed to remove port forward {local}: {e}')
                raise CommandExecutorError(f'Failed to remove port forward {local}: {e}') 