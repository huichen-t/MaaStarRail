"""
设备连接管理模块。
提供与Android设备的连接、通信和管理功能。
包括：
- ADB连接管理
- 设备检测和识别
- 包管理
- 端口转发
- 设备状态监控
"""

import ipaddress
import logging
import re
import socket
import subprocess
import time
from functools import wraps

import uiautomator2 as u2
from adbutils import AdbClient, AdbDevice, AdbTimeout, ForwardItem, ReverseItem
from adbutils.errors import AdbError

import module.config_src.server as server_
from module.base.decorator import Config, cached_property, del_cached_property, run_once
from module.base.timer import Timer
from module.base.utils import SelectedGrids, ensure_time
from module.device.connection_attr import ConnectionAttr
from module.device.env import IS_LINUX, IS_MACINTOSH, IS_WINDOWS
from module.device.method.utils import (PackageNotInstalled, RETRY_TRIES, get_serial_pair, handle_adb_error,
                                        handle_unknown_host_service, possible_reasons, random_port, recv_all,
                                        remove_shell_warning, retry_sleep)
from module.exception import EmulatorNotRunningError, RequestHumanTakeover
from module.base.logger import logger


def retry(func):
    """
    重试装饰器。
    用于处理ADB连接和命令执行时的各种异常情况。
    
    Args:
        func: 需要重试的函数
        
    Returns:
        function: 包装后的重试函数
    """
    @wraps(func)
    def retry_wrapper(self, *args, **kwargs):
        """
        Args:
            self (Adb): ADB实例
        """
        init = None
        for _ in range(RETRY_TRIES):
            try:
                if callable(init):
                    time.sleep(retry_sleep(_))
                    init()
                return func(self, *args, **kwargs)
            # 无法处理的异常
            except RequestHumanTakeover:
                break
            # ADB服务器被杀死时
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
            # 未知异常，可能是图像损坏
            except Exception as e:
                logger.exception(e)

                def init():
                    pass

        logger.critical(f'Retry {func.__name__}() failed')
        raise RequestHumanTakeover

    return retry_wrapper


class AdbDeviceWithStatus(AdbDevice):
    """
    带状态的ADB设备类。
    继承自AdbDevice，添加了设备状态信息。
    """
    def __init__(self, client: AdbClient, serial: str, status: str):
        self.status = status
        super().__init__(client, serial)

    def __str__(self):
        return f'AdbDevice({self.serial}, {self.status})'

    __repr__ = __str__

    def __bool__(self):
        return True

    @cached_property
    def port(self) -> int:
        """
        获取设备端口号。
        
        Returns:
            int: 端口号，如果无法获取则返回0
        """
        try:
            return int(self.serial.split(':')[1])
        except (IndexError, ValueError):
            return 0

    @cached_property
    def may_mumu12_family(self):
        """
        判断是否为MuMu12系列模拟器。
        通过端口号范围判断（16384-17408）。
        
        Returns:
            bool: 是否为MuMu12系列模拟器
        """
        # 127.0.0.1:16XXX
        return 16384 <= self.port <= 17408


class Connection(ConnectionAttr):
    """
    设备连接管理类。
    负责处理与Android设备的连接、通信和管理。
    """
    def __init__(self, config):
        """
        初始化连接管理器。
        
        Args:
            config (AzurLaneConfig, str): 用户配置名称或配置对象
        """
        super().__init__(config)
        if not self.is_over_http:
            self.detect_device()

        # 连接设备
        self.adb_connect(wait_device=False)
        logger.attr('AdbDevice', self.adb)

        # 包管理
        if self.config.is_cloud_game:
            self.package = server_.to_package(self.config.Emulator_PackageName, is_cloud=True)
        elif self.config.Emulator_PackageName == 'auto':
            self.detect_package()
        else:
            self.package = server_.to_package(self.config.Emulator_PackageName)
        logger.attr('Server', self.config.Emulator_PackageName)
        server_.server = self.config.Emulator_PackageName
        logger.attr('PackageName', self.package)
        server_.lang = self.config.Emulator_GameLanguage
        logger.attr('Lang', self.config.LANG)

        self.check_mumu_app_keep_alive()

    @Config.when(DEVICE_OVER_HTTP=False)
    def adb_command(self, cmd, timeout=10):
        """
        在子进程中执行ADB命令，通常用于传输大文件时。
        
        Args:
            cmd (list): 要执行的命令列表
            timeout (int): 超时时间，默认10秒
            
        Returns:
            str: 命令执行结果
        """
        cmd = list(map(str, cmd))
        cmd = [self.adb_binary, '-s', self.serial] + cmd
        return self.subprocess_run(cmd, timeout=timeout)

    def subprocess_run(self, cmd, timeout=10):
        """
        在子进程中执行命令。
        
        Args:
            cmd (list): 要执行的命令列表
            timeout (int): 超时时间，默认10秒
            
        Returns:
            str: 命令执行结果
        """
        logger.info(f'Execute: {cmd}')
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=False)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            logger.warning(f'TimeoutExpired when calling {cmd}, stdout={stdout}, stderr={stderr}')
        return stdout

    @Config.when(DEVICE_OVER_HTTP=True)
    def adb_command(self, cmd, timeout=10):
        """
        当通过HTTP连接时，adb_command()不可用。
        
        Args:
            cmd (list): 要执行的命令列表
            timeout (int): 超时时间，默认10秒
            
        Raises:
            RequestHumanTakeover: 当尝试通过HTTP连接执行ADB命令时抛出
        """
        logger.critical(
            f'Trying to execute {cmd}, '
            f'but adb_command() is not available when connecting over http: {self.serial}, '
        )
        raise RequestHumanTakeover

    def adb_start_server(self):
        """
        启动ADB服务器。
        使用`adb devices`命令作为`adb start-server`的替代，
        通过子进程启动ADB而不是通过socket连接，以杀死其他ADB进程。
        
        Returns:
            str: 命令执行结果
        """
        stdout = self.subprocess_run([self.adb_binary, 'devices'])
        logger.info(stdout)
        return stdout

    @Config.when(DEVICE_OVER_HTTP=False)
    def adb_shell(self, cmd, stream=False, recvall=True, timeout=10, rstrip=True):
        """
        执行adb shell命令，相当于`adb -s <serial> shell <*cmd>`。
        
        Args:
            cmd (list, str): 要执行的命令
            stream (bool): 是否返回流而不是字符串输出，默认False
            recvall (bool): 当stream=True时是否接收所有数据，默认True
            timeout (int): 超时时间，默认10秒
            rstrip (bool): 是否去除最后的空行，默认True
            
        Returns:
            str: 当stream=False时返回
            bytes: 当stream=True且recvall=True时返回
            socket: 当stream=True且recvall=False时返回
        """
        if not isinstance(cmd, str):
            cmd = list(map(str, cmd))

        if stream:
            result = self.adb.shell(cmd, stream=stream, timeout=timeout, rstrip=rstrip)
            if recvall:
                # bytes
                return recv_all(result)
            else:
                # socket
                return result
        else:
            result = self.adb.shell(cmd, stream=stream, timeout=timeout, rstrip=rstrip)
            result = remove_shell_warning(result)
            # str
            return result

    @Config.when(DEVICE_OVER_HTTP=True)
    def adb_shell(self, cmd, stream=False, recvall=True, timeout=10, rstrip=True):
        """
        通过HTTP执行shell命令，相当于http://127.0.0.1:7912/shell?command={command}。
        
        Args:
            cmd (list, str): 要执行的命令
            stream (bool): 是否返回流而不是字符串输出，默认False
            recvall (bool): 当stream=True时是否接收所有数据，默认True
            timeout (int): 超时时间，默认10秒
            rstrip (bool): 是否去除最后的空行，默认True
            
        Returns:
            str: 当stream=False时返回
            bytes: 当stream=True时返回
        """
        if not isinstance(cmd, str):
            cmd = list(map(str, cmd))

        if stream:
            result = self.u2.shell(cmd, stream=stream, timeout=timeout)
            # Already received all, so `recvall` is ignored
            result = remove_shell_warning(result.content)
            # bytes
            return result
        else:
            result = self.u2.shell(cmd, stream=stream, timeout=timeout).output
            if rstrip:
                result = result.rstrip()
            result = remove_shell_warning(result)
            # str
            return result

    def adb_getprop(self, name):
        """
        获取Android系统属性，相当于`getprop <name>`。
        
        Args:
            name (str): 属性名称
            
        Returns:
            str: 属性值
        """
        return self.adb_shell(['getprop', name]).strip()

    @cached_property
    @retry
    def cpu_abi(self) -> str:
        """
        获取设备的CPU架构。
        
        Returns:
            str: CPU架构，如arm64-v8a、armeabi-v7a、x86、x86_64
        """
        abi = self.adb_getprop('ro.product.cpu.abi')
        if not len(abi):
            logger.error(f'CPU ABI invalid: "{abi}"')
        return abi

    @cached_property
    @retry
    def sdk_ver(self) -> int:
        """
        获取Android SDK版本号。
        参考：https://apilevels.com/
        
        Returns:
            int: Android SDK版本号
        """
        sdk = self.adb_getprop('ro.build.version.sdk')
        try:
            return int(sdk)
        except ValueError:
            logger.error(f'SDK version invalid: {sdk}')

        return 0

    @cached_property
    @retry
    def is_avd(self):
        """
        判断是否为Android虚拟设备(AVD)。
        通过检查硬件信息判断。
        
        Returns:
            bool: 是否为AVD设备
        """
        if get_serial_pair(self.serial)[0] is None:
            return False
        if 'ranchu' in self.adb_getprop('ro.hardware'):
            return True
        if 'goldfish' in self.adb_getprop('ro.hardware.audio.primary'):
            return True
        return False

    @cached_property
    @retry
    def is_waydroid(self):
        """
        判断是否为Waydroid设备。
        通过检查产品品牌判断。
        
        Returns:
            bool: 是否为Waydroid设备
        """
        res = self.adb_getprop('ro.product.brand')
        logger.attr('ro.product.brand', res)
        return 'waydroid' in res.lower()

    @cached_property
    @retry
    def is_bluestacks_air(self):
        """
        判断是否为BlueStacks Air（Mac版BlueStacks）。
        通过检查系统属性和版本信息判断。
        
        Returns:
            bool: 是否为BlueStacks Air
        """
        # BlueStacks Air是Mac版本的BlueStacks
        if not IS_MACINTOSH:
            return False
        if not self.is_ldplayer_bluestacks_family:
            return False
        # [bst.installed_images]: [Tiramisu64]
        # [bst.instance]: [Tiramisu64]
        # Tiramisu64是Android 13，而BlueStacks Air是唯一使用Android 13的BlueStacks版本
        res = self.adb_getprop('bst.installed_images')
        logger.attr('bst.installed_images', res)
        if 'Tiramisu64' in res:
            return True
        return False

    @cached_property
    @retry
    def is_mumu_pro(self):
        """
        判断是否为MuMu Pro（Mac版MuMu）。
        通过检查系统属性和版本信息判断。
        
        Returns:
            bool: 是否为MuMu Pro
        """
        # MuMU Pro是Mac版本的MuMu
        if not IS_MACINTOSH:
            return False
        if not self.is_mumu_family:
            return False
        logger.attr('is_mumu_pro', True)
        return True

    @cached_property
    @retry
    def nemud_app_keep_alive(self) -> str:
        """
        获取MuMu模拟器的应用保活设置。
        
        Returns:
            str: 应用保活设置值
        """
        res = self.adb_getprop('nemud.app_keep_alive')
        logger.attr('nemud.app_keep_alive', res)
        return res

    @cached_property
    @retry
    def nemud_player_version(self) -> str:
        """
        获取MuMu模拟器的播放器版本。
        例如：[nemud.player_product_version]: [3.8.27.2950]
        
        Returns:
            str: 播放器版本号
        """
        res = self.adb_getprop('nemud.player_version')
        logger.attr('nemud.player_version', res)
        return res

    @cached_property
    @retry
    def nemud_player_engine(self) -> str:
        """
        获取MuMu模拟器的播放器引擎。
        可能的值：NEMUX或MACPRO
        
        Returns:
            str: 播放器引擎名称
        """
        res = self.adb_getprop('nemud.player_engine')
        logger.attr('nemud.player_engine', res)
        return res

    def check_mumu_app_keep_alive(self):
        """
        检查MuMu模拟器的应用保活设置。
        如果启用了保活功能，会提示用户关闭。
        
        Returns:
            bool: 检查是否通过
        """
        if not self.is_mumu_family:
            return False

        res = self.nemud_app_keep_alive
        if res == '':
            # 空属性，可能是MuMu6或MuMu12版本 < 3.5.6
            return True
        elif res == 'false':
            # 已禁用
            return True
        elif res == 'true':
            # https://mumu.163.com/help/20230802/35047_1102450.html
            logger.critical('请在MuMu模拟器设置内关闭 "后台挂机时保活运行"')
            raise RequestHumanTakeover
        else:
            logger.warning(f'Invalid nemud.app_keep_alive value: {res}')
            return False

    @cached_property
    def is_mumu_over_version_400(self) -> bool:
        """
        判断MuMu版本是否大于4.0。
        4.0及以上版本在getprop中没有信息。
        
        Returns:
            bool: 版本是否大于4.0
        """
        if not self.is_mumu_family:
            return False
        # >= 4.0 在getprop中没有信息
        if self.nemud_player_version == '':
            return True
        return False

    @cached_property
    def is_mumu_over_version_356(self) -> bool:
        """
        判断MuMu12版本是否大于等于3.5.6。
        该版本具有nemud.app_keep_alive属性且始终为竖屏设备。
        Mac上的MuMu PRO也具有相同特性。
        
        Returns:
            bool: 版本是否大于等于3.5.6
        """
        if not self.is_mumu_family:
            return False
        if self.is_mumu_over_version_400:
            return True
        if self.nemud_app_keep_alive != '':
            return True
        if IS_MACINTOSH:
            if 'MACPRO' in self.nemud_player_engine:
                return True
        return False

    @cached_property
    def _nc_server_host_port(self):
        """
        获取网络连接服务器的主机和端口信息。
        
        Returns:
            tuple: (server_listen_host, server_listen_port, client_connect_host, client_connect_port)
        """
        # 对于BlueStacks hyper-v，使用ADB反向连接
        if self.is_bluestacks_hyperv:
            host = '127.0.0.1'
            logger.info(f'Connecting to BlueStacks hyper-v, using host {host}')
            port = self.adb_reverse(f'tcp:{self.config.REVERSE_SERVER_PORT}')
            return host, port, host, self.config.REVERSE_SERVER_PORT
        # 对于模拟器，在当前主机上监听
        if self.is_emulator or self.is_over_http:
            # Mac模拟器
            if self.is_bluestacks_air or self.is_mumu_pro:
                logger.info(f'Connecting to local emulator, using host 127.0.0.1')
                port = random_port(self.config.FORWARD_PORT_RANGE)
                return '127.0.0.1', port, "10.0.2.2", port
            # 获取主机IP
            try:
                host = socket.gethostbyname(socket.gethostname())
            except socket.gaierror as e:
                logger.error(e)
                logger.error(f'Unknown host name: {socket.gethostname()}')
                host = '127.0.0.1'
            # 修复Linux AVD主机
            if IS_LINUX and host == '127.0.1.1':
                host = '127.0.0.1'
            logger.info(f'Connecting to local emulator, using host {host}')
            port = random_port(self.config.FORWARD_PORT_RANGE)
            # 对于AVD实例
            if self.is_avd:
                return host, port, "10.0.2.2", port
            return host, port, host, port
        # 对于本地网络设备，在与目标设备相同的网络下监听主机
        if self.is_network_device:
            hosts = socket.gethostbyname_ex(socket.gethostname())[2]
            logger.info(f'Current hosts: {hosts}')
            ip = ipaddress.ip_address(self.serial.split(':')[0])
            for host in hosts:
                if ip in ipaddress.ip_interface(f'{host}/24').network:
                    logger.info(f'Connecting to local network device, using host {host}')
                    port = random_port(self.config.FORWARD_PORT_RANGE)
                    return host, port, host, port
        # 对于其他设备，创建ADB反向连接并在127.0.0.1上监听
        host = '127.0.0.1'
        logger.info(f'Connecting to unknown device, using host {host}')
        port = self.adb_reverse(f'tcp:{self.config.REVERSE_SERVER_PORT}')
        return host, port, host, self.config.REVERSE_SERVER_PORT

    @cached_property
    def reverse_server(self):
        """
        在Alas上设置服务器，从模拟器访问。
        这将绕过adb shell并提高速度。
        
        Returns:
            socket: 服务器socket对象
        """
        del_cached_property(self, '_nc_server_host_port')
        host_port = self._nc_server_host_port
        logger.info(f'Reverse server listening on {host_port[0]}:{host_port[1]}, '
                    f'client can send data to {host_port[2]}:{host_port[3]}')
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(host_port[:2])
        server.settimeout(5)
        server.listen(5)
        return server

    @cached_property
    def nc_command(self):
        """
        获取netcat命令。
        
        Returns:
            list[str]: ['nc'] 或 ['busybox', 'nc']
        """
        if self.is_emulator:
            sdk = self.sdk_ver
            logger.info(f'sdk_ver: {sdk}')
            if sdk >= 28:
                # LD Player 9没有`nc`，尝试`busybox nc`
                # BlueStacks Pie (Android 9)有`nc`但无法发送数据，先尝试`busybox nc`
                trial = [
                    ['busybox', 'nc'],
                    ['nc'],
                ]
            else:
                trial = [
                    ['nc'],
                    ['busybox', 'nc'],
                ]
        else:
            trial = [
                ['nc'],
                ['busybox', 'nc'],
            ]
        for command in trial:
            # 大约3ms
            # 成功时应该返回命令帮助
            # nc: bad argument count (see "nc --help")
            result = self.adb_shell(command)
            # `/system/bin/sh: nc: not found`
            if 'not found' in result:
                continue
            # `/system/bin/sh: busybox: inaccessible or not found\n`
            if 'inaccessible' in result:
                continue
            logger.attr('nc command', command)
            return command

        logger.error('No `netcat` command available, please use screenshot methods without `_nc` suffix')
        raise RequestHumanTakeover

    def adb_shell_nc(self, cmd, timeout=5, chunk_size=262144):
        """
        使用netcat执行shell命令。
        
        Args:
            cmd (list): 要执行的命令
            timeout (int): 超时时间，默认5秒
            chunk_size (int): 数据块大小，默认262144
            
        Returns:
            bytes: 命令执行结果
        """
        # 服务器开始监听
        server = self.reverse_server
        server.settimeout(timeout)
        # 客户端发送数据，等待服务器接受
        # <command> | nc 127.0.0.1 {port}
        cmd += ["|", *self.nc_command, *self._nc_server_host_port[2:]]
        stream = self.adb_shell(cmd, stream=True, recvall=False)
        try:
            # 服务器接受连接
            conn, conn_port = server.accept()
        except socket.timeout:
            output = recv_all(stream, chunk_size=chunk_size)
            logger.warning(str(output))
            raise AdbTimeout('reverse server accept timeout')

        # 服务器接收数据
        data = recv_all(conn, chunk_size=chunk_size, recv_interval=0.001)

        # 服务器关闭连接
        conn.close()
        return data

    def adb_exec_out(self, cmd, serial=None):
        """
        执行adb exec-out命令。
        
        Args:
            cmd (list): 要执行的命令
            serial (str, optional): 设备序列号
            
        Returns:
            str: 命令执行结果
        """
        cmd.insert(0, 'exec-out')
        return self.adb_command(cmd, serial)

    def adb_forward(self, remote):
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
        port = 0
        for forward in self.adb.forward_list():
            if forward.serial == self.serial and forward.remote == remote and forward.local.startswith('tcp:'):
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
            port = random_port(self.config.FORWARD_PORT_RANGE)
            forward = ForwardItem(self.serial, f'tcp:{port}', remote)
            logger.info(f'Create forward: {forward}')
            self.adb.forward(forward.local, forward.remote)
            return port

    def adb_reverse(self, remote):
        """
        执行`adb reverse`命令，设置端口转发。
        
        Args:
            remote (str): 远程地址
            
        Returns:
            int: 端口号
        """
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
            port = random_port(self.config.FORWARD_PORT_RANGE)
            reverse = ReverseItem(f'tcp:{port}', remote)
            logger.info(f'Create reverse: {reverse}')
            self.adb.reverse(reverse.local, reverse.remote)
            return port

    def adb_forward_remove(self, local):
        """
        移除端口转发，相当于`adb -s <serial> forward --remove <local>`。
        当移除不存在的forward时不会抛出错误。
        
        Args:
            local (str): 本地地址，如'tcp:2437'
        """
        try:
            with self.adb_client._connect() as c:
                list_cmd = f"host-serial:{self.serial}:killforward:{local}"
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

    def adb_reverse_remove(self, local):
        """
        移除反向端口转发，相当于`adb -s <serial> reverse --remove <local>`。
        当移除不存在的reverse时不会抛出错误。
        
        Args:
            local (str): 本地地址，如'tcp:2437'
        """
        try:
            with self.adb_client._connect() as c:
                c.send_command(f"host:transport:{self.serial}")
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

    def adb_push(self, local, remote):
        """
        将文件推送到设备。
        
        Args:
            local (str): 本地文件路径
            remote (str): 远程文件路径
            
        Returns:
            str: 命令执行结果
        """
        cmd = ['push', local, remote]
        return self.adb_command(cmd)

    def _wait_device_appear(self, serial, first_devices=None):
        """
        等待设备出现。
        
        Args:
            serial (str): 设备序列号
            first_devices (list[AdbDeviceWithStatus], optional): 初始设备列表
            
        Returns:
            bool: 设备是否出现
        """
        # 等待时间略长于5秒
        timeout = Timer(5.2).start()
        first_log = True
        while 1:
            if first_devices is not None:
                devices = first_devices
                first_devices = None
            else:
                devices = self.list_device()
            # 检查设备是否出现
            for device in devices:
                if device.serial == serial and device.status == 'device':
                    return True
            # 延迟并稍后检查
            if timeout.reached():
                break
            if first_log:
                logger.info(f'Waiting device appear: {serial}')
                first_log = False
            time.sleep(0.05)

        return False

    @Config.when(DEVICE_OVER_HTTP=False)
    def adb_connect(self, wait_device=True):
        """
        连接到指定序列号的设备，最多尝试3次。
        如果有一个旧的ADB服务器在运行，而Alas使用的是较新的服务器（这种情况在中国模拟器中经常发生），
        第一次连接用于杀死另一个服务器，第二次才是真正的连接。
        
        Args:
            wait_device (bool): 是否等待模拟器和Android设备出现
            
        Returns:
            bool: 是否连接成功
        """
        # 在连接前断开离线设备
        devices = self.list_device()
        for device in devices:
            if device.status == 'offline':
                logger.warning(f'Device {device.serial} is offline, disconnect it before connecting')
                msg = self.adb_client.disconnect(device.serial)
                if msg:
                    logger.info(msg)
            elif device.status == 'unauthorized':
                logger.error(f'Device {device.serial} is unauthorized, please accept ADB debugging on your device')
            elif device.status == 'device':
                pass
            else:
                logger.warning(f'Device {device.serial} is is having a unknown status: {device.status}')

        # 跳过连接emulator-5554和Android手机，因为它们应该在插入时自动连接
        if 'emulator-' in self.serial:
            if wait_device:
                if self._wait_device_appear(self.serial, first_devices=devices):
                    logger.info(f'Serial {self.serial} connected')
                    return True
                else:
                    logger.info(f'Serial {self.serial} is not connected')
            logger.info(f'"{self.serial}" is a `emulator-*` serial, skip adb connect')
            return True
        if re.match(r'^[a-zA-Z0-9]+$', self.serial):
            if wait_device:
                if self._wait_device_appear(self.serial, first_devices=devices):
                    logger.info(f'Serial {self.serial} connected')
                    return True
                else:
                    logger.info(f'Serial {self.serial} is not connected')
            logger.info(f'"{self.serial}" seems to be a Android serial, skip adb connect')
            return True

        # 尝试连接
        for _ in range(3):
            msg = self.adb_client.connect(self.serial)
            logger.info(msg)
            # Connected to 127.0.0.1:59865
            # Already connected to 127.0.0.1:59865
            if 'connected' in msg:
                return True
            # bad port number '598265' in '127.0.0.1:598265'
            elif 'bad port' in msg:
                possible_reasons('Serial incorrect, might be a typo')
                raise RequestHumanTakeover
            # cannot connect to 127.0.0.1:55555:
            # No connection could be made because the target machine actively refused it. (10061)
            elif '(10061)' in msg:
                # MuMu12如果端口被占用可能会切换序列号
                # 暴力连接附近端口以处理序列号切换
                if self.is_mumu12_family:
                    before = self.serial
                    serial_list = [self.serial.replace(str(self.port), str(self.port + offset))
                                   for offset in [1, -1, 2, -2]]
                    self.adb_brute_force_connect(serial_list)
                    self.detect_device()
                    if self.serial != before:
                        return True
                # 没有这样的设备
                logger.warning('No such device exists, please restart the emulator or set a correct serial')
                raise EmulatorNotRunningError

        # 连接失败
        logger.warning(f'Failed to connect {self.serial} after 3 trial, assume connected')
        self.detect_device()
        return False

    def adb_brute_force_connect(self, serial_list):
        """
        暴力尝试连接多个序列号。
        
        Args:
            serial_list (list[str]): 要尝试连接的序列号列表
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        ev = asyncio.new_event_loop()
        pool = ThreadPoolExecutor(
            max_workers=len(serial_list),
            thread_name_prefix='adb_brute_force_connect',
        )

        def _connect(serial):
            msg = self.adb_client.connect(serial)
            logger.info(msg)
            return msg

        async def connect():
            tasks = [ev.run_in_executor(pool, _connect, serial) for serial in serial_list]
            await asyncio.gather(*tasks)

        ev.run_until_complete(connect())
        pool.shutdown(wait=False)
        ev.close()

    @Config.when(DEVICE_OVER_HTTP=True)
    def adb_connect(self, wait_device=True):
        """
        当通过HTTP连接时，跳过adb_connect()。
        
        Args:
            wait_device (bool): 是否等待设备出现
            
        Returns:
            bool: 始终返回True
        """
        # 通过HTTP连接时不需要adb连接
        return True

    def release_resource(self):
        """
        释放资源。
        删除缓存的属性。
        """
        del_cached_property(self, 'hermit_session')
        del_cached_property(self, 'droidcast_session')
        del_cached_property(self, '_minitouch_builder')
        del_cached_property(self, '_maatouch_builder')
        del_cached_property(self, 'reverse_server')

    def adb_disconnect(self):
        """
        断开ADB连接。
        释放相关资源。
        """
        msg = self.adb_client.disconnect(self.serial)
        if msg:
            logger.info(msg)
        self.release_resource()

    def adb_restart(self):
        """
        重启ADB客户端。
        """
        logger.info('Restart adb')
        # 杀死当前客户端
        self.adb_client.server_kill()
        # 初始化ADB客户端
        del_cached_property(self, 'adb_client')
        self.release_resource()
        _ = self.adb_client

    @Config.when(DEVICE_OVER_HTTP=False)
    def adb_reconnect(self):
        """
        如果没有找到设备则重启ADB客户端，否则尝试重新连接设备。
        """
        if self.config.Emulator_AdbRestart and len(self.list_device()) == 0:
            # 重启ADB
            self.adb_restart()
            # 连接设备
            self.adb_connect()
            self.detect_device()
        else:
            self.adb_disconnect()
            self.adb_connect()
            self.detect_device()

    @Config.when(DEVICE_OVER_HTTP=True)
    def adb_reconnect(self):
        """
        当通过HTTP连接时，跳过adb_reconnect()，可能需要手动重启ATX。
        """
        logger.warning(
            f'When connecting a device over http: {self.serial} '
            f'adb_reconnect() is skipped, you may need to restart ATX manually'
        )

    def install_uiautomator2(self):
        """
        初始化uiautomator2并移除minicap。
        """
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

    def uninstall_minicap(self):
        """
        卸载minicap，因为某些模拟器上minicap无法工作或会发送压缩图像。
        """
        logger.info('Removing minicap')
        self.adb_shell(["rm", "/data/local/tmp/minicap"])
        self.adb_shell(["rm", "/data/local/tmp/minicap.so"])

    @Config.when(DEVICE_OVER_HTTP=False)
    def restart_atx(self):
        """
        重启ATX。
        由于minitouch只支持一个连接，重启ATX以踢掉现有连接。
        """
        logger.info('Restart ATX')
        atx_agent_path = '/data/local/tmp/atx-agent'
        self.adb_shell([atx_agent_path, 'server', '--stop'])
        self.adb_shell([atx_agent_path, 'server', '--nouia', '-d', '--addr', '127.0.0.1:7912'])

    @Config.when(DEVICE_OVER_HTTP=True)
    def restart_atx(self):
        """
        当通过HTTP连接时，跳过restart_atx()，可能需要手动重启ATX。
        """
        logger.warning(
            f'When connecting a device over http: {self.serial} '
            f'restart_atx() is skipped, you may need to restart ATX manually'
        )

    @staticmethod
    def sleep(second):
        """
        休眠指定时间。
        
        Args:
            second(int, float, tuple): 休眠时间
        """
        time.sleep(ensure_time(second))

    _orientation_description = {
        0: 'Normal',
        1: 'HOME key on the right',
        2: 'HOME key on the top',
        3: 'HOME key on the left',
    }
    orientation = 0

    @retry
    def get_orientation(self):
        """
        获取设备屏幕方向。
        
        Returns:
            int: 屏幕方向值
                0: '正常'
                1: 'HOME键在右侧'
                2: 'HOME键在上方'
                3: 'HOME键在左侧'
        """
        _DISPLAY_RE = re.compile(
            r'.*DisplayViewport{.*valid=true, .*orientation=(?P<orientation>\d+), .*deviceWidth=(?P<width>\d+), deviceHeight=(?P<height>\d+).*'
        )
        output = self.adb_shell(['dumpsys', 'display'])

        res = _DISPLAY_RE.search(output, 0)

        if res:
            o = int(res.group('orientation'))
            if o in Connection._orientation_description:
                pass
            else:
                o = 0
                logger.warning(f'Invalid device orientation: {o}, assume it is normal')
        else:
            o = 0
            logger.warning('Unable to get device orientation, assume it is normal')

        self.orientation = o
        logger.attr('Device Orientation', f'{o} ({Connection._orientation_description.get(o, "Unknown")})')
        return o

    @retry
    def list_device(self):
        """
        获取已连接的设备列表。
        
        Returns:
            SelectedGrids[AdbDeviceWithStatus]: 设备列表
        """
        devices = []
        try:
            with self.adb_client._connect() as c:
                c.send_command("host:devices")
                c.check_okay()
                output = c.read_string_block()
                for line in output.splitlines():
                    parts = line.strip().split("\t")
                    if len(parts) != 2:
                        continue
                    device = AdbDeviceWithStatus(self.adb_client, parts[0], parts[1])
                    devices.append(device)
        except ConnectionResetError as e:
            # 仅在中国用户中出现
            # ConnectionResetError: [WinError 10054] 远程主机强迫关闭了一个现有的连接。
            logger.error(e)
            if '强迫关闭' in str(e):
                logger.critical('无法连接至ADB服务，请关闭UU加速器、原神私服、以及一些劣质代理软件。'
                                '它们会劫持电脑上所有的网络连接，包括Alas与模拟器之间的本地连接。')
        return SelectedGrids(devices)

    def detect_device(self):
        """
        检测可用设备。
        如果序列号为'auto'且只检测到一个设备，则使用该设备。
        """
        logger.hr('Detect device')
        available = SelectedGrids([])
        devices = SelectedGrids([])

        @run_once
        def brute_force_connect():
            """
            暴力连接模拟器。
            尝试连接所有可能的模拟器端口。
            """
            logger.info('Brute force connect')
            from deploy.Windows.emulator import EmulatorManager
            manager = EmulatorManager()
            manager.brute_force_connect()

        for _ in range(2):
            logger.info('Here are the available devices, '
                        'copy to Alas.Emulator.Serial to use it or set Alas.Emulator.Serial="auto"')
            devices = self.list_device()

            # 显示可用设备
            available = devices.select(status='device')
            for device in available:
                logger.info(device.serial)
            if not len(available):
                logger.info('No available devices')

            # 显示不可用设备（如果有）
            unavailable = devices.delete(available)
            if len(unavailable):
                logger.info('Here are the devices detected but unavailable')
                for device in unavailable:
                    logger.info(f'{device.serial} ({device.status})')

            # 暴力连接
            if self.config.Emulator_Serial == 'auto' and available.count == 0:
                logger.warning(f'No available device found')
                if IS_WINDOWS:
                    brute_force_connect()
                    continue
                else:
                    break
            else:
                break

        # 自动设备检测
        if self.config.Emulator_Serial == 'auto':
            if available.count == 0:
                logger.critical('No available device found, auto device detection cannot work, '
                                'please set an exact serial in Alas.Emulator.Serial instead of using "auto"')
                raise RequestHumanTakeover
            elif available.count == 1:
                logger.info(f'Auto device detection found only one device, using it')
                self.config.Emulator_Serial = self.serial = available[0].serial
                del_cached_property(self, 'adb')
            elif available.count == 2 \
                    and available.select(serial='127.0.0.1:7555') \
                    and available.select(may_mumu12_family=True):
                logger.info(f'Auto device detection found MuMu12 device, using it')
                # 对于MuMu12序列号，如127.0.0.1:7555和127.0.0.1:16384
                # 忽略7555使用16384
                remain = available.select(may_mumu12_family=True).first_or_none()
                self.config.Emulator_Serial = self.serial = remain.serial
                del_cached_property(self, 'adb')
            else:
                logger.critical('Multiple devices found, auto device detection cannot decide which to choose, '
                                'please copy one of the available devices listed above to Alas.Emulator.Serial')
                raise RequestHumanTakeover

        # 处理雷电模拟器
        # 雷电模拟器序列号在`127.0.0.1:5555+{X}`和`emulator-5554+{X}`之间跳转
        # 不写入config_src因为它是动态的
        port_serial, emu_serial = get_serial_pair(self.serial)
        if port_serial and emu_serial:
            # 可能是雷电模拟器，检查已连接设备
            port_device = devices.select(serial=port_serial).first_or_none()
            emu_device = devices.select(serial=emu_serial).first_or_none()
            if port_device and emu_device:
                # 找到配对设备，检查状态以获取正确的序列号
                if port_device.status == 'device' and emu_device.status == 'offline':
                    self.serial = port_serial
                    logger.info(f'LDPlayer device pair found: {port_device}, {emu_device}. '
                                f'Using serial: {self.serial}')
                elif port_device.status == 'offline' and emu_device.status == 'device':
                    self.serial = emu_serial
                    logger.info(f'LDPlayer device pair found: {port_device}, {emu_device}. '
                                f'Using serial: {self.serial}')
            elif not devices.select(serial=self.serial):
                # 当前序列号未找到
                if port_device and not emu_device:
                    logger.info(f'Current serial {self.serial} not found but paired device {port_serial} found. '
                                f'Using serial: {port_serial}')
                    self.serial = port_serial
                if not port_device and emu_device:
                    logger.info(f'Current serial {self.serial} not found but paired device {emu_serial} found. '
                                f'Using serial: {emu_serial}')
                    self.serial = emu_serial

        # 将MuMu12从127.0.0.1:7555重定向到127.0.0.1:16xxx
        if self.serial == '127.0.0.1:7555':
            for _ in range(2):
                mumu12 = available.select(may_mumu12_family=True)
                if mumu12.count == 1:
                    emu_serial = mumu12.first_or_none().serial
                    logger.warning(f'Redirect MuMu12 {self.serial} to {emu_serial}')
                    self.config.Emulator_Serial = self.serial = emu_serial
                    break
                elif mumu12.count >= 2:
                    logger.warning(f'Multiple MuMu12 serial found, cannot redirect')
                    break
                else:
                    # 只有127.0.0.1:7555
                    if self.is_mumu_over_version_356:
                        # is_mumu_over_version_356和nemud_app_keep_alive已被缓存
                        # 可以接受因为它是同一个设备
                        logger.warning(f'Device {self.serial} is MuMu12 but corresponding port not found')
                        if IS_WINDOWS:
                            brute_force_connect()
                        devices = self.list_device()
                        # 显示可用设备
                        available = devices.select(status='device')
                        for device in available:
                            logger.info(device.serial)
                        if not len(available):
                            logger.info('No available devices')
                        continue
                    else:
                        # MuMu6
                        break

        # MuMu12如果端口16384被占用会使用127.0.0.1:16385，自动重定向
        # 不写入config_src因为它是动态的
        if self.is_mumu12_family:
            matched = False
            for device in available.select(may_mumu12_family=True):
                if device.port == self.port:
                    # 精确匹配
                    matched = True
                    break
            if not matched:
                for device in available.select(may_mumu12_family=True):
                    if -2 <= device.port - self.port <= 2:
                        # 端口已切换
                        logger.info(f'MuMu12 serial switched {self.serial} -> {device.serial}')
                        del_cached_property(self, 'port')
                        del_cached_property(self, 'is_mumu12_family')
                        del_cached_property(self, 'is_mumu_family')
                        self.serial = device.serial
                        break

    @retry
    def list_package(self, show_log=True):
        """
        获取设备上所有已安装的包。
        优先使用dumpsys命令以加快速度。
        
        Args:
            show_log (bool): 是否显示日志
            
        Returns:
            list[str]: 包名列表
        """
        # 80ms
        if show_log:
            logger.info('Get package list')
        output = self.adb_shell(r'dumpsys package | grep "Package \["')
        packages = re.findall(r'Package \[([^\s]+)\]', output)
        if len(packages):
            return packages

        # 200ms
        if show_log:
            logger.info('Get package list')
        output = self.adb_shell(['pm', 'list', 'packages'])
        packages = re.findall(r'package:([^\s]+)', output)
        return packages

    def list_known_packages(self, show_log=True):
        """
        获取已知的包列表。
        
        Args:
            show_log (bool): 是否显示日志
            
        Returns:
            list[str]: 包名列表
        """
        packages = self.list_package(show_log=show_log)
        packages = [p for p in packages if p in server_.VALID_PACKAGE or p in server_.VALID_CLOUD_PACKAGE]
        return packages

    def detect_package(self, set_config=True):
        """
        检测设备上所有可能的包。
        显示与给定关键字匹配的包。
        
        Args:
            set_config (bool): 是否设置配置
        """
        logger.hr('Detect package')
        packages = self.list_known_packages()

        # 显示包
        logger.info(f'Here are the available packages in device "{self.serial}", '
                    f'copy to Alas.Emulator.PackageName to use it')
        if len(packages):
            for package in packages:
                logger.info(package)
        else:
            logger.info(f'No available packages on device "{self.serial}"')

        # 自动包检测
        if len(packages) == 0:
            logger.critical(f'No Star Rail package found, '
                            f'please confirm Star Rail has been installed on device "{self.serial}"')
            raise RequestHumanTakeover
        if len(packages) == 1:
            logger.info('Auto package detection found only one package, using it')
            self.package = packages[0]
            # 设置配置
            if set_config:
                with self.config.multi_set():
                    self.config.Emulator_PackageName = server_.to_server(self.package)
                    if self.package in server_.VALID_CLOUD_PACKAGE:
                        if self.config.Emulator_GameClient != 'cloud_android':
                            self.config.Emulator_GameClient = 'cloud_android'
                    else:
                        if self.config.Emulator_GameClient != 'android':
                            self.config.Emulator_GameClient = 'android'
            # 设置服务器
            # logger.info('Server changed, release resources')
            # set_server(self.package)
            return
        else:
            if self.config.is_cloud_game:
                packages = [p for p in packages if p in server_.VALID_CLOUD_PACKAGE]
                if len(packages) == 1:
                    logger.info('Auto package detection found only one package, using it')
                    self.package = packages[0]
                    if set_config:
                        self.config.Emulator_PackageName = server_.to_server(self.package)
                    return
            else:
                packages = [p for p in packages if p in server_.VALID_PACKAGE]
                if len(packages) == 1:
                    logger.info('Auto package detection found only one package, using it')
                    self.package = packages[0]
                    if set_config:
                        self.config.Emulator_PackageName = server_.to_server(self.package)
                    return
            logger.critical(
                f'Multiple Star Rail packages found, auto package detection cannot decide which to choose, '
                'please copy one of the available devices listed above to Alas.Emulator.PackageName')
            raise RequestHumanTakeover

    @cached_property
    def adb(self) -> AdbDevice:
        """
        获取ADB设备实例。
        根据配置选择不同的连接方式。
        
        Returns:
            AdbDevice: ADB设备实例
        """
        if self.is_over_http:
            return self.adb_over_http
        else:
            return self.adb_over_usb

    @cached_property
    def adb_over_usb(self) -> AdbDevice:
        """
        通过USB连接的ADB设备实例。
        优先使用配置的序列号，否则自动检测设备。
        
        Returns:
            AdbDevice: ADB设备实例
        """
        if self.config.Emulator_Serial:
            return AdbDeviceWithStatus(AdbClient(), self.config.Emulator_Serial, 'serial')
        else:
            return AdbDeviceWithStatus(AdbClient(), self.device_id, 'auto')

    @cached_property
    def adb_over_http(self) -> AdbDevice:
        """
        通过HTTP连接的ADB设备实例。
        使用HTTP代理方式连接设备。
        
        Returns:
            AdbDevice: ADB设备实例
        """
        return AdbDeviceWithStatus(AdbClient(), self.config.Emulator_Serial, 'http')

    @cached_property
    def device_id(self) -> str:
        """
        获取设备ID。
        根据不同的模拟器类型返回对应的设备ID。
        
        Returns:
            str: 设备ID
        """
        if self.is_mumu_family:
            return self.mumu_serial
        elif self.is_blue_stacks_family:
            return self.blue_stacks_serial
        elif self.is_ld_player_family:
            return self.ld_player_serial
        elif self.is_meizu_family:
            return self.meizu_serial
        elif self.is_oppo_family:
            return self.oppo_serial
        elif self.is_vivo_family:
            return self.vivo_serial
        elif self.is_xiaomi_family:
            return self.xiaomi_serial
        elif self.is_samsung_family:
            return self.samsung_serial
        elif self.is_huawei_family:
            return self.huawei_serial
        elif self.is_google_family:
            return self.google_serial
        elif self.is_sony_family:
            return self.sony_serial
        elif self.is_oneplus_family:
            return self.oneplus_serial
        elif self.is_asus_family:
            return self.asus_serial
        elif self.is_nokia_family:
            return self.nokia_serial
        elif self.is_htc_family:
            return self.htc_serial
        elif self.is_lg_family:
            return self.lg_serial
        elif self.is_motorola_family:
            return self.motorola_serial
        elif self.is_lenovo_family:
            return self.lenovo_serial
        elif self.is_zte_family:
            return self.zte_serial
        elif self.is_coolpad_family:
            return self.coolpad_serial
        elif self.is_gionee_family:
            return self.gionee_serial
        elif self.is_letv_family:
            return self.letv_serial
        elif self.is_other_family:
            return self.other_serial
        else:
            return self.auto_serial

    @cached_property
    def auto_serial(self) -> str:
        """
        自动检测设备序列号。
        通过ADB命令获取已连接设备的序列号。
        
        Returns:
            str: 设备序列号
        """
        devices = self.list_device()
        if not devices:
            raise EmulatorNotRunningError("No emulator detected")
        if len(devices) > 1:
            logger.warning(f'Multiple emulator detected: {devices}')
            logger.warning('Please specify Emulator_Serial in config/argument.yaml')
            logger.warning('Or use config/argument/override.yaml to specify different serial for different task')
        return devices[0].serial

    @cached_property
    def is_over_http(self):
        """
        判断是否使用HTTP连接。
        通过检查序列号是否包含http://或https://来判断。
        
        Returns:
            bool: 是否使用HTTP连接
        """
        return self.config.Emulator_Serial.startswith(('http://', 'https://'))

    @cached_property
    def is_mumu_family(self):
        """
        判断是否为MuMu系列模拟器。
        通过检查序列号是否包含mumu来判断。
        
        Returns:
            bool: 是否为MuMu系列模拟器
        """
        return 'mumu' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_blue_stacks_family(self):
        """
        判断是否为BlueStacks系列模拟器。
        通过检查序列号是否包含bluestacks来判断。
        
        Returns:
            bool: 是否为BlueStacks系列模拟器
        """
        return 'bluestacks' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_ld_player_family(self):
        """
        判断是否为雷电模拟器。
        通过检查序列号是否包含ldplayer来判断。
        
        Returns:
            bool: 是否为雷电模拟器
        """
        return 'ldplayer' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_meizu_family(self):
        """
        判断是否为魅族设备。
        通过检查序列号是否包含meizu来判断。
        
        Returns:
            bool: 是否为魅族设备
        """
        return 'meizu' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_oppo_family(self):
        """
        判断是否为OPPO设备。
        通过检查序列号是否包含oppo来判断。
        
        Returns:
            bool: 是否为OPPO设备
        """
        return 'oppo' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_vivo_family(self):
        """
        判断是否为vivo设备。
        通过检查序列号是否包含vivo来判断。
        
        Returns:
            bool: 是否为vivo设备
        """
        return 'vivo' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_xiaomi_family(self):
        """
        判断是否为小米设备。
        通过检查序列号是否包含xiaomi来判断。
        
        Returns:
            bool: 是否为小米设备
        """
        return 'xiaomi' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_samsung_family(self):
        """
        判断是否为三星设备。
        通过检查序列号是否包含samsung来判断。
        
        Returns:
            bool: 是否为三星设备
        """
        return 'samsung' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_huawei_family(self):
        """
        判断是否为华为设备。
        通过检查序列号是否包含huawei来判断。
        
        Returns:
            bool: 是否为华为设备
        """
        return 'huawei' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_google_family(self):
        """
        判断是否为谷歌设备。
        通过检查序列号是否包含google来判断。
        
        Returns:
            bool: 是否为谷歌设备
        """
        return 'google' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_sony_family(self):
        """
        判断是否为索尼设备。
        通过检查序列号是否包含sony来判断。
        
        Returns:
            bool: 是否为索尼设备
        """
        return 'sony' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_oneplus_family(self):
        """
        判断是否为一加设备。
        通过检查序列号是否包含oneplus来判断。
        
        Returns:
            bool: 是否为一加设备
        """
        return 'oneplus' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_asus_family(self):
        """
        判断是否为华硕设备。
        通过检查序列号是否包含asus来判断。
        
        Returns:
            bool: 是否为华硕设备
        """
        return 'asus' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_nokia_family(self):
        """
        判断是否为诺基亚设备。
        通过检查序列号是否包含nokia来判断。
        
        Returns:
            bool: 是否为诺基亚设备
        """
        return 'nokia' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_htc_family(self):
        """
        判断是否为HTC设备。
        通过检查序列号是否包含htc来判断。
        
        Returns:
            bool: 是否为HTC设备
        """
        return 'htc' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_lg_family(self):
        """
        判断是否为LG设备。
        通过检查序列号是否包含lg来判断。
        
        Returns:
            bool: 是否为LG设备
        """
        return 'lg' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_motorola_family(self):
        """
        判断是否为摩托罗拉设备。
        通过检查序列号是否包含motorola来判断。
        
        Returns:
            bool: 是否为摩托罗拉设备
        """
        return 'motorola' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_lenovo_family(self):
        """
        判断是否为联想设备。
        通过检查序列号是否包含lenovo来判断。
        
        Returns:
            bool: 是否为联想设备
        """
        return 'lenovo' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_zte_family(self):
        """
        判断是否为中兴设备。
        通过检查序列号是否包含zte来判断。
        
        Returns:
            bool: 是否为中兴设备
        """
        return 'zte' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_coolpad_family(self):
        """
        判断是否为酷派设备。
        通过检查序列号是否包含coolpad来判断。
        
        Returns:
            bool: 是否为酷派设备
        """
        return 'coolpad' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_gionee_family(self):
        """
        判断是否为金立设备。
        通过检查序列号是否包含gionee来判断。
        
        Returns:
            bool: 是否为金立设备
        """
        return 'gionee' in self.config.Emulator_Serial.lower()

    @cached_property
    def is_letv_family(self):
        """
        判断是否为乐视设备。
        通过检查序列号是否包含letv来判断。
        
        Returns:
            bool: 是否为乐视设备
        """
        return 'letv' in self.config.Emulator_Serial.lower()

    @cached_property
    def serial_360(self) -> str:
        """
        获取360设备的序列号。
        
        Returns:
            str: 360设备的序列号
        """
        return '127.0.0.1:5555'

    @cached_property
    def is_360_family(self):
        """
        判断是否为360设备。
        通过检查序列号是否包含360来判断。
        
        Returns:
            bool: 是否为360设备
        """
        return '360' in self.config.Emulator_Serial.lower()

    @cached_property
    def other_serial(self) -> str:
        """
        获取其他设备的序列号。
        
        Returns:
            str: 其他设备的序列号
        """
        return '127.0.0.1:5555'
