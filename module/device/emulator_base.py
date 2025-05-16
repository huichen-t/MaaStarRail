"""
模拟器基础模块
提供模拟器实例管理、路径处理、序列号处理等基础功能
"""

import os
import re
import typing as t
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, TypeVar

T = TypeVar("T")


class cached_property(Generic[T]):
    """
    缓存属性装饰器
    来自 https://github.com/pydanny/cached-property
    添加了类型支持

    一个只计算一次的属性,之后会替换为普通属性
    删除该属性会重置计算
    源码: https://github.com/bottlepy/bottle/commit/fa7733e075da0d790d809aa3d2f53071897e6f76
    """

    def __init__(self, func: Callable[..., T]):
        """
        初始化缓存属性装饰器
        
        Args:
            func: 要装饰的函数
        """
        self.func = func

    def __get__(self, obj, cls) -> T:
        """
        获取属性值
        第一次访问时计算结果并缓存
        后续访问直接返回缓存值
        
        Args:
            obj: 实例对象
            cls: 类对象
            
        Returns:
            T: 属性值
        """
        if obj is None:
            return self

        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


def iter_folder(folder, is_dir=False, ext=None):
    """
    遍历文件夹中的文件
    
    Args:
        folder (str): 要遍历的文件夹路径
        is_dir (bool): 是否只遍历目录
        ext (str): 文件扩展名过滤,如 '.yaml'

    Yields:
        str: 文件的绝对路径
    """
    try:
        files = os.listdir(folder)
    except FileNotFoundError:
        return

    for file in files:
        sub = os.path.join(folder, file)
        if is_dir:
            if os.path.isdir(sub):
                yield sub.replace('\\\\', '/').replace('\\', '/')
        elif ext is not None:
            if not os.path.isdir(sub):
                _, extension = os.path.splitext(file)
                if extension == ext:
                    yield os.path.join(folder, file).replace('\\\\', '/').replace('\\', '/')
        else:
            yield os.path.join(folder, file).replace('\\\\', '/').replace('\\', '/')


def iter_process() -> "Iterable[tuple[int, list[str]]]":
    """
    遍历系统中的进程
    
    Yields:
        tuple: (进程ID, 命令行参数列表)
        命令行参数列表保证至少有一个元素
    """
    try:
        import psutil
    except ModuleNotFoundError:
        return

    if psutil.WINDOWS:
        # 由于这是一次性使用,我们直接访问psutil._psplatform.Process
        # 绕过psutil.Process.is_running()的调用
        # 这只需要约0.017秒
        # 如果使用psutil.process_iter(['pid', 'cmdline'])则需要超过1秒
        import psutil._psutil_windows as cetx
        for pid in psutil.pids():
            # 0和4总是在任务管理器和进程查看器中显示
            if pid == 0 or pid == 4:
                continue
            try:
                # 在psutil<=5.9.8上这会很快,总共需要0.027秒
                # 但在psutil>=6.0.0上需要0.39秒
                cmdline = cetx.proc_cmdline(pid, use_peb=True)
            except (psutil.AccessDenied, psutil.NoSuchProcess, IndexError, OSError):
                # psutil.AccessDenied: 访问被拒绝
                # NoSuchProcess: 进程不再存在(pid=xxx)
                # ProcessLookupError: [Errno 3] 假设没有此进程(源自psutil_pid_is_running -> 0)
                # OSError: [WinError 87] 参数错误(源自ReadProcessMemory)
                continue

            # 验证命令行
            if not cmdline:
                continue
            try:
                exe = cmdline[0]
            except IndexError:
                continue
            # \??\C:\Windows\system32\conhost.exe
            if exe.startswith(r'\??'):
                continue
            yield pid, cmdline
    else:
        # 尚未优化
        for pid in psutil.pids():
            proc = psutil._psplatform.Process(pid)
            try:
                cmdline = proc.cmdline()
            except (psutil.AccessDenied, psutil.NoSuchProcess, IndexError, OSError):
                continue

            # 验证命令行
            if not cmdline:
                continue
            try:
                cmdline[0]
            except IndexError:
                continue
            yield pid, cmdline


def abspath(path):
    """
    将路径转换为绝对路径并统一使用正斜杠
    
    Args:
        path: 输入路径
        
    Returns:
        str: 标准化后的绝对路径
    """
    return os.path.abspath(path).replace('\\', '/')


def get_serial_pair(serial):
    """
    获取模拟器序列号对应的端口对
    
    Args:
        serial (str): 设备序列号

    Returns:
        tuple: (127.0.0.1:端口号, emulator-端口号) 或 (None, None)
        例如: ('127.0.0.1:5555', 'emulator-5554')
    """
    if serial.startswith('127.0.0.1:'):
        try:
            port = int(serial[10:])
            if 5555 <= port <= 5555 + 32:
                return f'127.0.0.1:{port}', f'emulator-{port - 1}'
        except (ValueError, IndexError):
            pass
    if serial.startswith('emulator-'):
        try:
            port = int(serial[9:])
            if 5554 <= port <= 5554 + 32:
                return f'127.0.0.1:{port + 1}', f'emulator-{port}'
        except (ValueError, IndexError):
            pass

    return None, None


def remove_duplicated_path(paths):
    """
    移除重复的路径(不区分大小写)
    
    Args:
        paths (list[str]): 路径列表

    Returns:
        list[str]: 去重后的路径列表
    """
    paths = sorted(set(paths))
    dic = {}
    for path in paths:
        dic.setdefault(path.lower(), path)
    return list(dic.values())


@dataclass
class EmulatorInstanceBase:
    """
    模拟器实例基类
    用于表示一个模拟器实例的基本信息
    """
    # ADB连接用的序列号
    serial: str
    # 模拟器实例名称,用于启动/停止模拟器
    name: str
    # 模拟器可执行文件路径
    path: str

    def __str__(self):
        return f'{self.type}(serial="{self.serial}", name="{self.name}", path="{self.path}")'

    @cached_property
    def type(self) -> str:
        """
        获取模拟器类型
        
        Returns:
            str: 模拟器类型,如 Emulator.NoxPlayer
        """
        return self.emulator.type

    @cached_property
    def emulator(self):
        """
        获取模拟器对象
        
        Returns:
            Emulator: 模拟器实例
        """
        return EmulatorBase(self.path)

    def __eq__(self, other):
        """
        比较两个模拟器实例是否相等
        支持与字符串、列表和EmulatorInstanceBase对象比较
        """
        if isinstance(other, str) and self.type == other:
            return True
        if isinstance(other, list) and self.type in other:
            return True
        if isinstance(other, EmulatorInstanceBase):
            return super().__eq__(other) and self.type == other.type
        return super().__eq__(other)

    def __hash__(self):
        return hash(str(self))

    def __bool__(self):
        return True

    @cached_property
    def MuMuPlayer12_id(self):
        """
        获取MuMu 12模拟器的实例ID
        
        支持的实例名称格式:
            MuMuPlayer-12.0-3
            YXArkNights-12.0-1

        Returns:
            int: 实例ID,如果不是MuMu 12实例则返回None
        """
        res = re.search(r'MuMuPlayer(?:Global)?-12.0-(\d+)', self.name)
        if res:
            return int(res.group(1))
        res = re.search(r'YXArkNights-12.0-(\d+)', self.name)
        if res:
            return int(res.group(1))

        return None

    @cached_property
    def LDPlayer_id(self):
        """
        获取雷电模拟器的实例ID
        
        支持的实例名称格式:
            leidian0
            leidian1

        Returns:
            int: 实例ID,如果不是雷电模拟器实例则返回None
        """
        res = re.search(r'leidian(\d+)', self.name)
        if res:
            return int(res.group(1))

        return None


class EmulatorBase:
    """
    模拟器基类
    定义各种模拟器类型和基础功能
    """
    # 这些值必须与argument.yaml中EmulatorInfo.Emulator.option匹配
    NoxPlayer = 'NoxPlayer'
    NoxPlayer64 = 'NoxPlayer64'
    NoxPlayerFamily = [NoxPlayer, NoxPlayer64]
    BlueStacks4 = 'BlueStacks4'
    BlueStacks5 = 'BlueStacks5'
    BlueStacks4HyperV = 'BlueStacks4HyperV'
    BlueStacks5HyperV = 'BlueStacks5HyperV'
    BlueStacksFamily = [BlueStacks4, BlueStacks5]
    LDPlayer3 = 'LDPlayer3'
    LDPlayer4 = 'LDPlayer4'
    LDPlayer9 = 'LDPlayer9'
    LDPlayerFamily = [LDPlayer3, LDPlayer4, LDPlayer9]
    MuMuPlayer = 'MuMuPlayer'
    MuMuPlayerX = 'MuMuPlayerX'
    MuMuPlayer12 = 'MuMuPlayer12'
    MuMuPlayerFamily = [MuMuPlayer, MuMuPlayerX, MuMuPlayer12]
    MEmuPlayer = 'MEmuPlayer'

    @classmethod
    def path_to_type(cls, path: str) -> str:
        """
        根据可执行文件路径判断模拟器类型
        
        Args:
            path: 可执行文件路径

        Returns:
            str: 模拟器类型,如Emulator.NoxPlayer
                如果不是模拟器则返回空字符串
        """
        return ''

    def iter_instances(self) -> t.Iterable[EmulatorInstanceBase]:
        """
        遍历当前模拟器的所有实例
        
        Yields:
            EmulatorInstance: 模拟器实例
        """
        pass

    def iter_adb_binaries(self) -> t.Iterable[str]:
        """
        遍历当前模拟器中的adb可执行文件
        
        Yields:
            str: adb可执行文件路径
        """
        pass

    def __init__(self, path):
        """
        初始化模拟器对象
        
        Args:
            path: 模拟器可执行文件路径
        """
        # 可执行文件路径
        self.path = path.replace('\\', '/')
        # 模拟器目录路径
        self.dir = os.path.dirname(path)
        # 模拟器类型,如果不是模拟器则为空字符串
        self.type = self.__class__.path_to_type(path)

    def __eq__(self, other):
        """
        比较两个模拟器是否相等
        支持与字符串和列表比较
        """
        if isinstance(other, str) and self.type == other:
            return True
        if isinstance(other, list) and self.type in other:
            return True
        return super().__eq__(other)

    def __str__(self):
        return f'{self.type}(path="{self.path}")'

    __repr__ = __str__

    def __hash__(self):
        return hash(self.path)

    def __bool__(self):
        return True

    def abspath(self, path, folder=None):
        """
        获取绝对路径
        
        Args:
            path: 相对路径
            folder: 基础目录,默认为模拟器目录

        Returns:
            str: 绝对路径
        """
        if folder is None:
            folder = self.dir
        return abspath(os.path.join(folder, path))

    @classmethod
    def is_emulator(cls, path: str) -> bool:
        """
        判断路径是否为模拟器可执行文件
        
        Args:
            path: 可执行文件路径

        Returns:
            bool: 是否为模拟器
        """
        return bool(cls.path_to_type(path))

    def list_folder(self, folder, is_dir=False, ext=None):
        """
        安全地列出目录中的文件
        
        Args:
            folder: 目录路径
            is_dir: 是否只列出目录
            ext: 文件扩展名过滤

        Returns:
            list[str]: 文件路径列表
        """
        folder = self.abspath(folder)
        return list(iter_folder(folder, is_dir=is_dir, ext=ext))


class EmulatorManagerBase:
    """
    模拟器管理器基类
    提供模拟器实例管理的基础功能
    """
    @staticmethod
    def iter_running_emulator():
        """
        遍历正在运行的模拟器
        
        Yields:
            str: 模拟器可执行文件路径,可能包含重复值
        """
        return

    @cached_property
    def all_emulators(self) -> t.List[EmulatorBase]:
        """
        获取当前计算机上安装的所有模拟器
        
        Returns:
            list[EmulatorBase]: 模拟器对象列表
        """
        return []

    @cached_property
    def all_emulator_instances(self) -> t.List[EmulatorInstanceBase]:
        """
        获取当前计算机上安装的所有模拟器实例
        
        Returns:
            list[EmulatorInstanceBase]: 模拟器实例列表
        """
        return []

    @cached_property
    def all_emulator_serials(self) -> t.List[str]:
        """
        获取当前计算机上所有可能的模拟器序列号
        
        Returns:
            list[str]: 序列号列表
        """
        out = []
        for emulator in self.all_emulator_instances:
            out.append(emulator.serial)
            # 同时添加emulator-5554格式的序列号
            port_serial, emu_serial = get_serial_pair(emulator.serial)
            if emu_serial:
                out.append(emu_serial)
        return out

    @cached_property
    def all_adb_binaries(self) -> t.List[str]:
        """
        获取当前计算机上所有模拟器的adb可执行文件
        
        Returns:
            list[str]: adb可执行文件路径列表
        """
        out = []
        for emulator in self.all_emulators:
            for exe in emulator.iter_adb_binaries():
                out.append(exe)
        return out
