"""
配置监视器模块，用于监控配置文件的变化。
当配置文件被修改时，可以触发重新加载配置。
"""

import os
from datetime import datetime

from module.config_src.utils import filepath_config, DEFAULT_TIME
from module.base.logger import logger


class ConfigWatcher:
    """
    配置监视器类，用于监控配置文件的变化
    
    属性:
        config_name: 配置文件名，默认为'alas'
        start_mtime: 开始监视时的时间戳，默认为DEFAULT_TIME
    """
    config_name = 'alas'
    start_mtime = DEFAULT_TIME

    def start_watching(self) -> None:
        """
        开始监视配置文件
        记录当前配置文件的修改时间作为基准时间
        """
        self.start_mtime = self.get_mtime()

    def get_mtime(self) -> datetime:
        """
        获取配置文件的最后修改时间
        
        Returns:
            datetime: 配置文件的最后修改时间（精确到秒）
        """
        timestamp = os.stat(filepath_config(self.config_name)).st_mtime
        mtime = datetime.fromtimestamp(timestamp).replace(microsecond=0)
        return mtime

    def should_reload(self) -> bool:
        """
        检查配置文件是否需要重新加载
        
        通过比较当前文件的修改时间和开始监视时的时间来判断
        如果当前修改时间大于开始监视时的时间，说明文件被修改过
        
        Returns:
            bool: 如果配置文件被修改过，返回True，否则返回False
        """
        mtime = self.get_mtime()
        if mtime > self.start_mtime:
            logger.info(f'Config "{self.config_name}" changed at {mtime}')
            return True
        else:
            return False
