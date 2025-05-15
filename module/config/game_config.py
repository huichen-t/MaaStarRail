"""
游戏配置模块，管理游戏相关的配置。
包括游戏参数、界面元素、任务配置等。
"""

from typing import Dict, List, Tuple, Union

from module.config.base_config import BaseConfig


class GameConfig(BaseConfig):
    """
    游戏配置类，管理游戏相关的配置。
    
    主要功能：
    - 游戏参数配置
    - 界面元素配置
    - 任务配置管理
    """
    
    def __init__(self, config_name: str = "game_config.json"):
        """
        初始化游戏配置。
        
        Args:
            config_name (str): 配置文件名，默认为 game_config.json
        """
        super().__init__(config_name)
        self._init_default_config()
        
    def _init_default_config(self) -> None:
        """初始化默认配置"""
        # 游戏参数
        self.set_value("game.params.wait_timeout", 10)
        self.set_value("game.params.click_interval", 0.5)
        self.set_value("game.params.swipe_duration", 0.5)
        self.set_value("game.params.drag_duration", 0.5)
        
        # 界面元素
        self.set_value("game.ui.main_menu", {
            "name": "主菜单",
            "template": "main_menu.png",
            "position": (100, 100),
            "click_offset": (10, 10)
        })
        
        self.set_value("game.ui.battle", {
            "name": "战斗界面",
            "template": "battle.png",
            "position": (200, 200),
            "click_offset": (10, 10)
        })
        
        # 任务配置
        self.set_value("game.tasks.daily", {
            "name": "日常任务",
            "enabled": True,
            "priority": 1,
            "subtasks": ["login", "claim_rewards", "complete_daily"]
        })
        
        self.set_value("game.tasks.weekly", {
            "name": "周常任务",
            "enabled": True,
            "priority": 2,
            "subtasks": ["complete_weekly", "claim_weekly_rewards"]
        })
        
    @property
    def WAIT_TIMEOUT(self) -> int:
        """等待超时时间（秒）"""
        return self.get_value("game.params.wait_timeout", 10)
        
    @property
    def CLICK_INTERVAL(self) -> float:
        """点击间隔时间（秒）"""
        return self.get_value("game.params.click_interval", 0.5)
        
    @property
    def SWIPE_DURATION(self) -> float:
        """滑动持续时间（秒）"""
        return self.get_value("game.params.swipe_duration", 0.5)
        
    @property
    def DRAG_DURATION(self) -> float:
        """拖拽持续时间（秒）"""
        return self.get_value("game.params.drag_duration", 0.5)
        
    def get_ui_element(self, element_name: str) -> Dict[str, Union[str, Tuple[int, int]]]:
        """
        获取界面元素配置。
        
        Args:
            element_name (str): 界面元素名称
            
        Returns:
            Dict[str, Union[str, Tuple[int, int]]]: 界面元素配置
        """
        return self.get_value(f"game.ui.{element_name}", {})
        
    def get_task_config(self, task_name: str) -> Dict[str, Union[str, bool, int, List[str]]]:
        """
        获取任务配置。
        
        Args:
            task_name (str): 任务名称
            
        Returns:
            Dict[str, Union[str, bool, int, List[str]]]: 任务配置
        """
        return self.get_value(f"game.tasks.{task_name}", {})
        
    def is_task_enabled(self, task_name: str) -> bool:
        """
        检查任务是否启用。
        
        Args:
            task_name (str): 任务名称
            
        Returns:
            bool: 任务是否启用
        """
        task_config = self.get_task_config(task_name)
        return task_config.get("enabled", False)
        
    def get_task_priority(self, task_name: str) -> int:
        """
        获取任务优先级。
        
        Args:
            task_name (str): 任务名称
            
        Returns:
            int: 任务优先级
        """
        task_config = self.get_task_config(task_name)
        return task_config.get("priority", 0)
        
    def get_task_subtasks(self, task_name: str) -> List[str]:
        """
        获取任务子任务列表。
        
        Args:
            task_name (str): 任务名称
            
        Returns:
            List[str]: 子任务列表
        """
        task_config = self.get_task_config(task_name)
        return task_config.get("subtasks", [])
        
    def update_ui_element(self, element_name: str, config: Dict[str, Union[str, Tuple[int, int]]]) -> None:
        """
        更新界面元素配置。
        
        Args:
            element_name (str): 界面元素名称
            config (Dict[str, Union[str, Tuple[int, int]]]): 新的配置
        """
        self.set_value(f"game.ui.{element_name}", config)
        
    def update_task_config(self, task_name: str, config: Dict[str, Union[str, bool, int, List[str]]]) -> None:
        """
        更新任务配置。
        
        Args:
            task_name (str): 任务名称
            config (Dict[str, Union[str, bool, int, List[str]]]): 新的配置
        """
        self.set_value(f"game.tasks.{task_name}", config) 