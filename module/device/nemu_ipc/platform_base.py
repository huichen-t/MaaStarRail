"""
平台基础模块
提供模拟器平台的基础接口和功能实现
"""

import sys
import typing as t

from pydantic import BaseModel

from module.base.decorator import cached_property, del_cached_property
from module.base.utils import SelectedGrids
from module.device.connection import Connection
from module.device.method.utils import get_serial_pair
from module.device.platform.emulator_base import EmulatorInstanceBase, EmulatorManagerBase, remove_duplicated_path
from module.logger import logger


class EmulatorInfo(BaseModel):
    """
    模拟器信息类
    用于存储模拟器的基本信息
    """
    # 模拟器类型
    emulator: str = ''
    # 模拟器实例名称
    name: str = ''
    # 模拟器可执行文件路径
    path: str = ''

    # 用于手机云平台API的配置
    # access_key: SecretStr = ''
    # secret: SecretStr = ''


class PlatformBase(EmulatorManagerBase):
    """
    平台基类
    提供各种操作系统或手机云平台的基础接口
    
    每个Platform类必须实现以下API:
    - all_emulators(): 获取所有模拟器
    - all_emulator_instances(): 获取所有模拟器实例
    - emulator_start(): 启动模拟器
    - emulator_stop(): 停止模拟器
    """

    def emulator_start(self):
        """
        启动模拟器,直到启动完成
        
        要求:
        - 需要实现重试机制
        - 禁止使用简单的sleep等待启动
        """
        logger.info(f'当前平台 {sys.platform} 不支持emulator_start,跳过')

    def emulator_stop(self):
        """
        停止模拟器
        """
        logger.info(f'当前平台 {sys.platform} 不支持emulator_stop,跳过')

    @cached_property
    def emulator_info(self) -> EmulatorInfo:
        """
        获取模拟器信息
        
        Returns:
            EmulatorInfo: 包含模拟器类型、名称和路径的信息对象
        """
        emulator = self.config.EmulatorInfo_Emulator
        if emulator == 'auto':
            emulator = ''

        def parse_info(value):
            """
            解析配置信息
            
            Args:
                value: 配置值
                
            Returns:
                str: 处理后的配置值
            """
            if isinstance(value, str):
                value = value.strip().replace('\n', '')
                if value in ['None', 'False', 'True']:
                    value = ''
                return value
            else:
                return ''

        name = parse_info(self.config.EmulatorInfo_name)
        path = parse_info(self.config.EmulatorInfo_path)

        return EmulatorInfo(
            emulator=emulator,
            name=name,
            path=path,
        )

    @cached_property
    def emulator_instance(self) -> t.Optional[EmulatorInstanceBase]:
        """
        获取当前模拟器实例
        
        Returns:
            EmulatorInstanceBase: 模拟器实例对象,如果未找到则返回None
        """
        data = self.emulator_info
        old_info = dict(
            emulator=data.emulator,
            path=data.path,
            name=data.name,
        )
        # 将emulator-5554重定向到127.0.0.1:5555
        serial = self.serial
        port_serial, _ = get_serial_pair(self.serial)
        if port_serial is not None:
            serial = port_serial

        instance = self.find_emulator_instance(
            serial=serial,
            name=data.name,
            path=data.path,
            emulator=data.emulator,
        )

        # 写入完整的模拟器数据
        if instance is not None:
            new_info = dict(
                emulator=instance.type,
                path=instance.path,
                name=instance.name,
            )
            if new_info != old_info:
                with self.config.multi_set():
                    self.config.EmulatorInfo_Emulator = instance.type
                    self.config.EmulatorInfo_name = instance.name
                    self.config.EmulatorInfo_path = instance.path
                del_cached_property(self, 'emulator_info')

        return instance

    def find_emulator_instance(
            self,
            serial: str,
            name: str = None,
            path: str = None,
            emulator: str = None
    ) -> t.Optional[EmulatorInstanceBase]:
        """
        查找模拟器实例
        
        Args:
            serial: 序列号,如 "127.0.0.1:5555"
            name: 实例名称,如 "Nougat64"
            path: 模拟器安装路径,如 "C:/Program Files/BlueStacks_nxt/HD-Player.exe"
            emulator: 模拟器类型,如 "BlueStacks5"

        Returns:
            EmulatorInstance: 模拟器实例,如果未找到则返回None
        """
        logger.hr('查找模拟器实例', level=2)
        instances = SelectedGrids(self.all_emulator_instances)
        for instance in instances:
            logger.info(instance)
        search_args = dict(serial=serial)

        # 通过序列号搜索
        select = instances.select(**search_args)
        if select.count == 0:
            logger.warning(f'未找到序列号为 {search_args} 的模拟器实例,序列号无效')
            return None
        if select.count == 1:
            instance = select[0]
            logger.hr('模拟器实例', level=2)
            logger.info(f'找到模拟器实例: {instance}')
            return instance

        # 在给定序列号中有多个实例,通过名称搜索
        if name:
            search_args['name'] = name
            select = instances.select(**search_args)
            if select.count == 0:
                logger.warning(f'未找到名称为 {search_args} 的模拟器实例,名称无效')
                search_args.pop('name')
            elif select.count == 1:
                instance = select[0]
                logger.hr('模拟器实例', level=2)
                logger.info(f'找到模拟器实例: {instance}')
                return instance

        # 在给定序列号和名称中有多个实例,通过路径搜索
        if path:
            search_args['path'] = path
            select = instances.select(**search_args)
            if select.count == 0:
                logger.warning(f'未找到路径为 {search_args} 的模拟器实例,路径无效')
                search_args.pop('path')
            elif select.count == 1:
                instance = select[0]
                logger.hr('模拟器实例', level=2)
                logger.info(f'找到模拟器实例: {instance}')
                return instance

        # 在给定序列号、名称和路径中有多个实例,通过模拟器类型搜索
        if emulator:
            search_args['type'] = emulator
            select = instances.select(**search_args)
            if select.count == 0:
                logger.warning(f'未找到类型为 {search_args} 的模拟器实例,类型无效')
                search_args.pop('type')
            elif select.count == 1:
                instance = select[0]
                logger.hr('模拟器实例', level=2)
                logger.info(f'找到模拟器实例: {instance}')
                return instance

        # 仍然有多个实例,从正在运行的模拟器中搜索
        running = remove_duplicated_path(list(self.iter_running_emulator()))
        logger.info('正在运行的模拟器')
        for exe in running:
            logger.info(exe)
        if len(running) == 1:
            logger.info('只有一个正在运行的模拟器')
            # 与路径搜索相同
            search_args['path'] = running[0]
            select = instances.select(**search_args)
            if select.count == 0:
                logger.warning(f'未找到路径为 {search_args} 的模拟器实例,路径无效')
                search_args.pop('path')
            elif select.count == 1:
                instance = select[0]
                logger.hr('模拟器实例', level=2)
                logger.info(f'找到模拟器实例: {instance}')
                return instance

        # 仍然有多个实例
        logger.warning(f'找到多个匹配 {search_args} 的模拟器实例')
        return None
