"""
Windows平台模拟器管理模块
提供Windows系统下模拟器的检测、管理和实例化功能
"""

import codecs
import os
import re
import typing as t
import winreg
from dataclasses import dataclass

# module/device/platform/emulator_base.py
# module/device/platform/emulator_windows.py
# Will be used in Alas Easy Install, they shouldn't import any Alas modules.
from module.device.platform.emulator_base import EmulatorBase, EmulatorInstanceBase, EmulatorManagerBase, \
    remove_duplicated_path
from module.device.platform.utils import cached_property, iter_folder, iter_process


@dataclass
class RegValue:
    """
    注册表值数据类
    用于存储注册表键值信息
    """
    name: str  # 键名
    value: str  # 键值
    typ: int   # 类型


def list_reg(reg) -> t.List[RegValue]:
    """
    列出注册表键下的所有值
    
    Args:
        reg: 注册表键对象
        
    Returns:
        list[RegValue]: 注册表值列表
    """
    rows = []
    index = 0
    try:
        while 1:
            value = RegValue(*winreg.EnumValue(reg, index))
            index += 1
            rows.append(value)
    except OSError:
        pass
    return rows


def list_key(reg) -> t.List[RegValue]:
    """
    列出注册表键下的所有子键
    
    Args:
        reg: 注册表键对象
        
    Returns:
        list[RegValue]: 子键列表
    """
    rows = []
    index = 0
    try:
        while 1:
            value = winreg.EnumKey(reg, index)
            index += 1
            rows.append(value)
    except OSError:
        pass
    return rows


def abspath(path):
    """
    将路径转换为绝对路径并统一使用正斜杠
    
    Args:
        path: 输入路径
        
    Returns:
        str: 标准化后的绝对路径
    """
    return os.path.abspath(path).replace('\\', '/')


class EmulatorInstance(EmulatorInstanceBase):
    """
    Windows平台模拟器实例类
    继承自EmulatorInstanceBase,提供Windows特定的实例管理功能
    """
    @cached_property
    def emulator(self):
        """
        获取模拟器对象
        
        Returns:
            Emulator: 模拟器实例
        """
        return Emulator(self.path)


class Emulator(EmulatorBase):
    """
    Windows平台模拟器类
    继承自EmulatorBase,提供Windows特定的模拟器管理功能
    """
    @classmethod
    def path_to_type(cls, path: str) -> str:
        """
        根据可执行文件路径判断模拟器类型
        
        Args:
            path: 可执行文件路径(不区分大小写)

        Returns:
            str: 模拟器类型,如Emulator.NoxPlayer
        """
        folder, exe = os.path.split(path)
        folder, dir1 = os.path.split(folder)
        folder, dir2 = os.path.split(folder)
        exe = exe.lower()
        dir1 = dir1.lower()
        dir2 = dir2.lower()
        if exe == 'nox.exe':
            if dir2 == 'nox':
                return cls.NoxPlayer
            elif dir2 == 'nox64':
                return cls.NoxPlayer64
            else:
                return cls.NoxPlayer
        if exe == 'bluestacks.exe':
            if dir1 in ['bluestacks', 'bluestacks_cn']:
                return cls.BlueStacks4
            elif dir1 in ['bluestacks_nxt', 'bluestacks_nxt_cn']:
                return cls.BlueStacks5
            else:
                return cls.BlueStacks4
        if exe == 'hd-player.exe':
            if dir1 in ['bluestacks', 'bluestacks_cn']:
                return cls.BlueStacks4
            elif dir1 in ['bluestacks_nxt', 'bluestacks_nxt_cn']:
                return cls.BlueStacks5
            else:
                return cls.BlueStacks5
        if exe == 'dnplayer.exe':
            if dir1 == 'ldplayer':
                return cls.LDPlayer3
            elif dir1 == 'ldplayer4':
                return cls.LDPlayer4
            elif dir1 == 'ldplayer9':
                return cls.LDPlayer9
            else:
                return cls.LDPlayer3
        if exe == 'nemuplayer.exe':
            if dir2 == 'nemu':
                return cls.MuMuPlayer
            elif dir2 == 'nemu9':
                return cls.MuMuPlayerX
            else:
                return cls.MuMuPlayer
        if exe == 'mumuplayer.exe':
            return cls.MuMuPlayer12
        if exe == 'memu.exe':
            return cls.MEmuPlayer

        return ''

    @staticmethod
    def multi_to_single(exe):
        """
        将多实例管理器路径转换为单实例可执行文件路径
        
        Args:
            exe (str): 模拟器可执行文件路径

        Yields:
            str: 模拟器可执行文件路径
        """
        if 'HD-MultiInstanceManager.exe' in exe:
            yield exe.replace('HD-MultiInstanceManager.exe', 'HD-Player.exe')
            yield exe.replace('HD-MultiInstanceManager.exe', 'Bluestacks.exe')
        elif 'MultiPlayerManager.exe' in exe:
            yield exe.replace('MultiPlayerManager.exe', 'Nox.exe')
        elif 'dnmultiplayer.exe' in exe:
            yield exe.replace('dnmultiplayer.exe', 'dnplayer.exe')
        elif 'NemuMultiPlayer.exe' in exe:
            yield exe.replace('NemuMultiPlayer.exe', 'NemuPlayer.exe')
        elif 'MuMuMultiPlayer.exe' in exe:
            yield exe.replace('MuMuMultiPlayer.exe', 'MuMuPlayer.exe')
        elif 'MuMuManager.exe' in exe:
            yield exe.replace('MuMuManager.exe', 'MuMuPlayer.exe')
        elif 'MEmuConsole.exe' in exe:
            yield exe.replace('MEmuConsole.exe', 'MEmu.exe')
        else:
            yield exe

    @staticmethod
    def single_to_console(exe: str):
        """
        将单实例可执行文件路径转换为控制台路径
        
        Args:
            exe (str): 模拟器可执行文件路径

        Returns:
            str: 控制台可执行文件路径
        """
        if 'MuMuPlayer.exe' in exe:
            return exe.replace('MuMuPlayer.exe', 'MuMuManager.exe')
        elif 'LDPlayer.exe' in exe:
            return exe.replace('LDPlayer.exe', 'ldconsole.exe')
        elif 'dnplayer.exe' in exe:
            return exe.replace('dnplayer.exe', 'ldconsole.exe')
        elif 'Bluestacks.exe' in exe:
            return exe.replace('Bluestacks.exe', 'bsconsole.exe')
        elif 'MEmu.exe' in exe:
            return exe.replace('MEmu.exe', 'memuc.exe')
        else:
            return exe

    @staticmethod
    def vbox_file_to_serial(file: str) -> str:
        """
        从vbox文件中提取序列号
        
        Args:
            file: vbox文件路径

        Returns:
            str: 序列号,如'127.0.0.1:5555'
        """
        regex = re.compile('<*?hostport="(.*?)".*?guestport="5555"/>')
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f.readlines():
                    # <Forwarding name="port2" proto="1" hostip="127.0.0.1" hostport="62026" guestport="5555"/>
                    res = regex.search(line)
                    if res:
                        return f'127.0.0.1:{res.group(1)}'
            return ''
        except FileNotFoundError:
            return ''

    def iter_instances(self):
        """
        遍历当前模拟器的所有实例
        
        Yields:
            EmulatorInstance: 模拟器实例
        """
        if self == Emulator.NoxPlayerFamily:
            # ./BignoxVMS/{name}/{name}.vbox
            for folder in self.list_folder('./BignoxVMS', is_dir=True):
                for file in iter_folder(folder, ext='.vbox'):
                    serial = Emulator.vbox_file_to_serial(file)
                    if serial:
                        yield EmulatorInstance(
                            serial=serial,
                            name=os.path.basename(folder),
                            path=self.path,
                        )
        elif self == Emulator.BlueStacks5:
            # 获取UserDefinedDir,BlueStacks存储数据的位置
            folder = None
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\BlueStacks_nxt") as reg:
                    folder = winreg.QueryValueEx(reg, 'UserDefinedDir')[0]
            except FileNotFoundError:
                pass
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\BlueStacks_nxt_cn") as reg:
                    folder = winreg.QueryValueEx(reg, 'UserDefinedDir')[0]
            except FileNotFoundError:
                pass
            if not folder:
                return
            # 读取{UserDefinedDir}/bluestacks.conf
            try:
                with open(self.abspath('./bluestacks.conf', folder), encoding='utf-8') as f:
                    content = f.read()
            except FileNotFoundError:
                return
            # bst.instance.Nougat64.adb_port="5555"
            emulators = re.findall(r'bst.instance.(\w+).status.adb_port="(\d+)"', content)
            for emulator in emulators:
                yield EmulatorInstance(
                    serial=f'127.0.0.1:{emulator[1]}',
                    name=emulator[0],
                    path=self.path,
                )
        elif self == Emulator.BlueStacks4:
            # ../Engine/Android
            regex = re.compile(r'^Android')
            for folder in self.list_folder('../Engine', is_dir=True):
                folder = os.path.basename(folder)
                res = regex.match(folder)
                if not res:
                    continue
                # BlueStacks4的序列号不是静态的,每次启动模拟器都会增加
                # 假设都使用127.0.0.1:5555
                yield EmulatorInstance(
                    serial=f'127.0.0.1:5555',
                    name=folder,
                    path=self.path
                )
        elif self == Emulator.LDPlayerFamily:
            # ./vms/leidian0
            regex = re.compile(r'^leidian(\d+)$')
            for folder in self.list_folder('./vms', is_dir=True):
                folder = os.path.basename(folder)
                res = regex.match(folder)
                if not res:
                    continue
                # LDPlayer在.vbox文件中没有转发端口配置
                # 端口自动递增,5555,5557,5559等
                port = int(res.group(1)) * 2 + 5555
                yield EmulatorInstance(
                    serial=f'127.0.0.1:{port}',
                    name=folder,
                    path=self.path
                )
        elif self == Emulator.MuMuPlayer:
            # MuMu没有多实例,只在7555端口
            yield EmulatorInstance(
                serial='127.0.0.1:7555',
                name='',
                path=self.path,
            )
        elif self == Emulator.MuMuPlayerX:
            # vms/nemu-12.0-x64-default
            for folder in self.list_folder('../vms', is_dir=True):
                for file in iter_folder(folder, ext='.nemu'):
                    serial = Emulator.vbox_file_to_serial(file)
                    if serial:
                        yield EmulatorInstance(
                            serial=serial,
                            name=os.path.basename(folder),
                            path=self.path,
                        )
        elif self == Emulator.MuMuPlayer12:
            # vms/MuMuPlayer-12.0-0
            for folder in self.list_folder('../vms', is_dir=True):
                for file in iter_folder(folder, ext='.nemu'):
                    serial = Emulator.vbox_file_to_serial(file)
                    name = os.path.basename(folder)
                    if serial:
                        yield EmulatorInstance(
                            serial=serial,
                            name=name,
                            path=self.path,
                        )
                    # 修复MuMu12 v4.0.4,其默认实例在vbox配置中没有转发记录
                    else:
                        instance = EmulatorInstance(
                            serial=serial,
                            name=name,
                            path=self.path,
                        )
                        if instance.MuMuPlayer12_id:
                            instance.serial = f'127.0.0.1:{16384 + 32 * instance.MuMuPlayer12_id}'
                            yield instance
        elif self == Emulator.MEmuPlayer:
            # ./MemuHyperv VMs/{name}/{name}.memu
            for folder in self.list_folder('./MemuHyperv VMs', is_dir=True):
                for file in iter_folder(folder, ext='.memu'):
                    serial = Emulator.vbox_file_to_serial(file)
                    if serial:
                        yield EmulatorInstance(
                            serial=serial,
                            name=os.path.basename(folder),
                            path=self.path,
                        )

    def iter_adb_binaries(self) -> t.Iterable[str]:
        """
        遍历当前模拟器中的adb可执行文件
        
        Yields:
            str: adb可执行文件路径
        """
        if self == Emulator.NoxPlayerFamily:
            exe = self.abspath('./nox_adb.exe')
            if os.path.exists(exe):
                yield exe
        if self == Emulator.MuMuPlayerFamily:
            # 从MuMu9\emulator\nemu9\EmulatorShell
            # 到MuMu9\emulator\nemu9\vmonitor\bin\adb_server.exe
            exe = self.abspath('../vmonitor/bin/adb_server.exe')
            if os.path.exists(exe):
                yield exe

        # 所有模拟器都有adb.exe
        exe = self.abspath('./adb.exe')
        if os.path.exists(exe):
            yield exe


class EmulatorManager:
    """
    Windows平台模拟器管理器
    提供Windows系统下模拟器的检测、管理和实例化功能
    """
    @staticmethod
    def iter_user_assist():
        """
        获取UserAssist中最近执行的程序
        https://github.com/forensicmatt/MonitorUserAssist

        Yields:
            str: 模拟器可执行文件路径,可能包含重复值
        """
        path = r'Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist'
        # {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}\xxx.exe
        regex_hash = re.compile(r'{.*}')
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as reg:
                folders = list_key(reg)
        except FileNotFoundError:
            return

        for folder in folders:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f'{path}\\{folder}\\Count') as reg:
                    for key in list_reg(reg):
                        key = codecs.decode(key.name, 'rot-13')
                        # 跳过带哈希的
                        if regex_hash.search(key):
                            continue
                        for file in Emulator.multi_to_single(key):
                            yield file
            except FileNotFoundError:
                # FileNotFoundError: [WinError 2] 系统找不到指定的文件。
                # 可能是没有"Count"子目录的随机目录
                continue

    @staticmethod
    def iter_mui_cache():
        """
        遍历曾经运行过的模拟器可执行文件
        http://what-when-how.com/windows-forensic-analysis/registry-analysis-windows-forensic-analysis-part-8/
        https://3gstudent.github.io/%E6%B8%97%E9%80%8F%E6%8A%80%E5%B7%A7-Windows%E7%B3%BB%E7%BB%9F%E6%96%87%E4%BB%B6%E6%89%A7%E8%A1%8C%E8%AE%B0%E5%BD%95%E7%9A%84%E8%8E%B7%E5%8F%96%E4%B8%8E%E6%B8%85%E9%99%A4

        Yields:
            str: 模拟器可执行文件路径,可能包含重复值
        """
        path = r'Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as reg:
                rows = list_reg(reg)
        except FileNotFoundError:
            return

        regex = re.compile(r'(^.*\.exe)\.')
        for row in rows:
            res = regex.search(row.name)
            if not res:
                continue
            for file in Emulator.multi_to_single(res.group(1)):
                yield file

    @staticmethod
    def get_install_dir_from_reg(path, key):
        """
        从注册表获取安装目录
        
        Args:
            path (str): 注册表路径,如'SOFTWARE\\leidian\\ldplayer'
            key (str): 键名,如'InstallDir'

        Returns:
            str: 安装目录或None
        """
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as reg:
                root = winreg.QueryValueEx(reg, key)[0]
                return root
        except FileNotFoundError:
            pass
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as reg:
                root = winreg.QueryValueEx(reg, key)[0]
                return root
        except FileNotFoundError:
            pass

        return None

    @staticmethod
    def iter_uninstall_registry():
        """
        遍历注册表中的模拟器卸载程序

        Yields:
            str: 卸载程序可执行文件路径
        """
        known_uninstall_registry_path = [
            r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
            r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
        ]
        known_emulator_registry_name = [
            'Nox',
            'Nox64',
            'BlueStacks',
            'BlueStacks_nxt',
            'BlueStacks_cn',
            'BlueStacks_nxt_cn',
            'LDPlayer',
            'LDPlayer4',
            'LDPlayer9',
            'leidian',
            'leidian4',
            'leidian9',
            'Nemu',
            'Nemu9',
            'MuMuPlayer-12.0'
            'MEmu',
        ]
        for path in known_uninstall_registry_path:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as reg:
                    software_list = list_key(reg)
            except FileNotFoundError:
                continue
            for software in software_list:
                if software not in known_emulator_registry_name:
                    continue
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f'{path}\\{software}') as software_reg:
                        uninstall = winreg.QueryValueEx(software_reg, 'UninstallString')[0]
                except FileNotFoundError:
                    continue
                if not uninstall:
                    continue
                # UninstallString格式如:
                # C:\Program Files\BlueStacks_nxt\BlueStacksUninstaller.exe -tmp
                # "E:\ProgramFiles\Microvirt\MEmu\uninstall\uninstall.exe" -u
                # 提取""中的路径
                res = re.search('"(.*?)"', uninstall)
                uninstall = res.group(1) if res else uninstall
                yield uninstall

    @staticmethod
    def iter_running_emulator():
        """
        遍历正在运行的模拟器
        
        Yields:
            str: 模拟器可执行文件路径,可能包含重复值
        """
        for pid, cmdline in iter_process():
            exe = cmdline[0]
            if Emulator.is_emulator(exe):
                yield exe

    @cached_property
    def all_emulators(self) -> t.List[Emulator]:
        """
        获取当前计算机上安装的所有模拟器
        
        Returns:
            list[Emulator]: 模拟器对象列表
        """
        exe = set([])

        # MuiCache
        for file in EmulatorManager.iter_mui_cache():
            if Emulator.is_emulator(file) and os.path.exists(file):
                exe.add(file)

        # UserAssist
        for file in EmulatorManager.iter_user_assist():
            if Emulator.is_emulator(file) and os.path.exists(file):
                exe.add(file)

        # LDPlayer安装路径
        for path in [r'SOFTWARE\leidian\ldplayer',
                     r'SOFTWARE\leidian\ldplayer9']:
            ld = self.get_install_dir_from_reg(path, 'InstallDir')
            if ld:
                ld = abspath(os.path.join(ld, './dnplayer.exe'))
                if Emulator.is_emulator(ld) and os.path.exists(ld):
                    exe.add(ld)

        # 卸载注册表
        for uninstall in EmulatorManager.iter_uninstall_registry():
            # 从卸载程序查找模拟器可执行文件
            for file in iter_folder(abspath(os.path.dirname(uninstall)), ext='.exe'):
                if Emulator.is_emulator(file) and os.path.exists(file):
                    exe.add(file)
            # 从父目录查找
            for file in iter_folder(abspath(os.path.join(os.path.dirname(uninstall), '../')), ext='.exe'):
                if Emulator.is_emulator(file) and os.path.exists(file):
                    exe.add(file)
            # MuMu特定目录
            for file in iter_folder(abspath(os.path.join(os.path.dirname(uninstall), 'EmulatorShell')), ext='.exe'):
                if Emulator.is_emulator(file) and os.path.exists(file):
                    exe.add(file)

        # 正在运行
        for file in EmulatorManager.iter_running_emulator():
            if os.path.exists(file):
                exe.add(file)

        # 去重
        exe = [Emulator(path).path for path in exe if Emulator.is_emulator(path)]
        exe = [Emulator(path) for path in remove_duplicated_path(exe)]
        return exe

    @cached_property
    def all_emulator_instances(self) -> t.List[EmulatorInstance]:
        """
        获取当前计算机上安装的所有模拟器实例
        
        Returns:
            list[EmulatorInstance]: 模拟器实例列表
        """
        instances = []
        for emulator in self.all_emulators:
            instances += list(emulator.iter_instances())

        instances: t.List[EmulatorInstance] = sorted(instances, key=lambda x: str(x))
        return instances

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


if __name__ == '__main__':
    self = EmulatorManager()
    for emu in self.all_emulator_instances:
        print(emu)
