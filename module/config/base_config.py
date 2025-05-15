"""
配置基类模块，提供基础的配置功能。
包括配置的加载、保存、更新等基本操作。
"""

import json
import os
from typing import Any, Dict

from module.base.logger import logger


class BaseConfig:
    """
    配置基类，提供基础配置功能。
    
    主要功能：
    - 配置文件的加载和保存
    - 配置值的获取和设置
    - 配置的自动更新
    """
    
    def __init__(self, config_name: str):
        """
        初始化配置。
        
        Args:
            config_name (str): 配置文件名
        """
        self.config_name = config_name
        self.config_path = os.path.join("config", config_name)
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """
        从配置文件加载配置。
        如果配置文件不存在，则创建默认配置。
        """
        try:
            # 确保配置目录存在
            os.makedirs("config", exist_ok=True)
            
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"配置已从 {self.config_path} 加载")
            else:
                logger.info(f"配置文件 {self.config_path} 不存在，将创建默认配置")
                self.save()  # 保存默认配置
                
        except Exception as e:
            logger.error(f"加载配置失败: {str(e)}")
            raise
    
    def save(self) -> None:
        """
        保存配置到文件。
        如果配置目录不存在，则创建目录。
        """
        try:
            # 确保配置目录存在
            os.makedirs("config", exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)
            logger.info(f"配置已保存到 {self.config_path}")
            
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}")
            raise
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值。
        
        Args:
            key (str): 配置键，支持点号分隔的路径
            default (Any): 默认值，如果配置不存在则返回此值
            
        Returns:
            Any: 配置值
        """
        try:
            value = self._config
            for k in key.split('.'):
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_value(self, key: str, value: Any) -> None:
        """
        设置配置值。
        
        Args:
            key (str): 配置键，支持点号分隔的路径
            value (Any): 配置值
        """
        try:
            keys = key.split('.')
            target = self._config
            
            # 遍历路径，创建必要的字典
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            
            # 设置值
            target[keys[-1]] = value
            
            # 自动保存配置
            self.save()
            
        except Exception as e:
            logger.error(f"设置配置值失败: {str(e)}")
            raise
    
    def update(self, config_dict: Dict[str, Any]) -> None:
        """
        批量更新配置。
        
        Args:
            config_dict (Dict[str, Any]): 要更新的配置字典
        """
        try:
            self._config.update(config_dict)
            self.save()
        except Exception as e:
            logger.error(f"更新配置失败: {str(e)}")
            raise 