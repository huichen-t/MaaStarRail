"""
配置管理器模块，提供全局配置访问接口。
使用单例模式确保配置实例的唯一性。
"""

from typing import Dict, Optional

from module.config.platform_config import PlatformConfig
from module.config.game_config import GameConfig
from module.base.logger import logger


class ConfigManager:
    """
    配置管理器类，使用单例模式管理所有配置实例。
    
    主要功能：
    - 统一管理所有配置实例
    - 提供全局访问接口
    - 确保配置实例的唯一性
    """
    
    _instance: Optional['ConfigManager'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'ConfigManager':
        """
        实现单例模式。
        
        Returns:
            ConfigManager: 配置管理器实例
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """
        初始化配置管理器。
        确保只初始化一次。
        """
        if not self._initialized:
            self._configs: Dict[str, object] = {}
            self._initialized = True
            self._init_configs()
    
    def _init_configs(self) -> None:
        """初始化所有配置实例"""
        try:
            # 初始化平台配置
            self._configs['platform'] = PlatformConfig()
            logger.info("平台配置初始化成功")
            
            # 初始化游戏配置
            self._configs['game'] = GameConfig()
            logger.info("游戏配置初始化成功")
            
        except Exception as e:
            logger.error(f"配置初始化失败: {str(e)}")
            raise
    
    @property
    def platform(self) -> PlatformConfig:
        """
        获取平台配置实例。
        
        Returns:
            PlatformConfig: 平台配置实例
        """
        return self._configs.get('platform')
    
    @property
    def game(self) -> GameConfig:
        """
        获取游戏配置实例。
        
        Returns:
            GameConfig: 游戏配置实例
        """
        return self._configs.get('game')
    
    def reload_all(self) -> None:
        """重新加载所有配置"""
        try:
            for config in self._configs.values():
                if hasattr(config, 'load'):
                    config.load()
            logger.info("所有配置重新加载成功")
        except Exception as e:
            logger.error(f"配置重新加载失败: {str(e)}")
            raise
    
    def save_all(self) -> None:
        """保存所有配置"""
        try:
            for config in self._configs.values():
                if hasattr(config, 'save'):
                    config.save()
            logger.info("所有配置保存成功")
        except Exception as e:
            logger.error(f"配置保存失败: {str(e)}")
            raise


# 创建全局配置管理器实例
config_manager = ConfigManager() 