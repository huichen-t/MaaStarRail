"""
平台配置模块，管理平台相关的配置。
包括设备配置、应用配置和连接配置等。
"""

from typing import Tuple

from module.config.base_config import BaseConfig


class PlatformConfig(BaseConfig):
    """
    平台配置类，管理平台相关的配置。
    
    主要功能：
    - 设备配置管理
    - 应用配置管理
    - 连接配置管理
    """
    
    def __init__(self, config_name: str = "platform_config.json"):
        """
        初始化平台配置。
        
        Args:
            config_name (str): 配置文件名，默认为 platform_config.json
        """
        super().__init__(config_name)
        self._init_default_config()
        
    def _init_default_config(self) -> None:
        """初始化默认配置"""
        # 设备配置
        self.set_value("device.over_http", False)
        self.set_value("device.resolution", (1280, 720))
        self.set_value("device.forward_port_range", (20000, 21000))
        self.set_value("device.reverse_server_port", 7903)
        
        # 设备工具路径
        self.set_value("device.tools.minitouch.remote", "/data/local/tmp/minitouch")
        self.set_value("device.tools.maatouch.local", "./bin/MaaTouch/maatouch")
        self.set_value("device.tools.maatouch.remote", "/data/local/tmp/maatouch")
        self.set_value("device.tools.ascreencap.local", "./bin/ascreencap")
        self.set_value("device.tools.ascreencap.remote", "/data/local/tmp/ascreencap")
        
        # DroidCast配置
        self.set_value("device.tools.droidcast.version", "DroidCast")
        self.set_value("device.tools.droidcast.local", "./bin/DroidCast/DroidCast-debug-1.1.0.apk")
        self.set_value("device.tools.droidcast.remote", "/data/local/tmp/DroidCast.apk")
        self.set_value("device.tools.droidcast.raw.local", "./bin/DroidCast/DroidCastS-release-1.1.5.apk")
        self.set_value("device.tools.droidcast.raw.remote", "/data/local/tmp/DroidCastS.apk")
        
        # Hermit配置
        self.set_value("device.tools.hermit.local", "./bin/hermit/hermit.apk")
        
        # Scrcpy配置
        self.set_value("device.tools.scrcpy.local", "./bin/scrcpy/scrcpy-server-v1.20.jar")
        self.set_value("device.tools.scrcpy.remote", "/data/local/tmp/scrcpy-server-v1.20.jar")
        
        # 应用配置
        self.set_value("app.assets.folder", "./assets")
        self.set_value("app.assets.module", "./tasks")
        
        # 基础参数
        self.set_value("app.params.color_similar_threshold", 10)
        self.set_value("app.params.button_offset", (20, 20))
        self.set_value("app.params.button_match_similarity", 0.85)
        self.set_value("app.params.wait_before_saving_screen_shot", 1)
        
    @property
    def DEVICE_OVER_HTTP(self) -> bool:
        """是否使用HTTP通信"""
        return self.get_value("device.over_http", False)
        
    @property
    def DEVICE_RESOLUTION(self) -> Tuple[int, int]:
        """设备分辨率"""
        return self.get_value("device.resolution", (1280, 720))
        
    @property
    def FORWARD_PORT_RANGE(self) -> Tuple[int, int]:
        """端口转发范围"""
        return self.get_value("device.forward_port_range", (20000, 21000))
        
    @property
    def REVERSE_SERVER_PORT(self) -> int:
        """反向服务器端口"""
        return self.get_value("device.reverse_server_port", 7903)
        
    @property
    def MINITOUCH_FILEPATH_REMOTE(self) -> str:
        """minitouch远程路径"""
        return self.get_value("device.tools.minitouch.remote", "/data/local/tmp/minitouch")
        
    @property
    def MAATOUCH_FILEPATH_LOCAL(self) -> str:
        """maatouch本地路径"""
        return self.get_value("device.tools.maatouch.local", "./bin/MaaTouch/maatouch")
        
    @property
    def MAATOUCH_FILEPATH_REMOTE(self) -> str:
        """maatouch远程路径"""
        return self.get_value("device.tools.maatouch.remote", "/data/local/tmp/maatouch")
        
    @property
    def ASCREENCAP_FILEPATH_LOCAL(self) -> str:
        """ascreencap本地路径"""
        return self.get_value("device.tools.ascreencap.local", "./bin/ascreencap")
        
    @property
    def ASCREENCAP_FILEPATH_REMOTE(self) -> str:
        """ascreencap远程路径"""
        return self.get_value("device.tools.ascreencap.remote", "/data/local/tmp/ascreencap")
        
    @property
    def DROIDCAST_VERSION(self) -> str:
        """DroidCast版本"""
        return self.get_value("device.tools.droidcast.version", "DroidCast")
        
    @property
    def DROIDCAST_FILEPATH_LOCAL(self) -> str:
        """DroidCast本地路径"""
        return self.get_value("device.tools.droidcast.local", "./bin/DroidCast/DroidCast-debug-1.1.0.apk")
        
    @property
    def DROIDCAST_FILEPATH_REMOTE(self) -> str:
        """DroidCast远程路径"""
        return self.get_value("device.tools.droidcast.remote", "/data/local/tmp/DroidCast.apk")
        
    @property
    def DROIDCAST_RAW_FILEPATH_LOCAL(self) -> str:
        """DroidCast Raw本地路径"""
        return self.get_value("device.tools.droidcast.raw.local", "./bin/DroidCast/DroidCastS-release-1.1.5.apk")
        
    @property
    def DROIDCAST_RAW_FILEPATH_REMOTE(self) -> str:
        """DroidCast Raw远程路径"""
        return self.get_value("device.tools.droidcast.raw.remote", "/data/local/tmp/DroidCastS.apk")
        
    @property
    def HERMIT_FILEPATH_LOCAL(self) -> str:
        """Hermit本地路径"""
        return self.get_value("device.tools.hermit.local", "./bin/hermit/hermit.apk")
        
    @property
    def SCRCPY_FILEPATH_LOCAL(self) -> str:
        """Scrcpy本地路径"""
        return self.get_value("device.tools.scrcpy.local", "./bin/scrcpy/scrcpy-server-v1.20.jar")
        
    @property
    def SCRCPY_FILEPATH_REMOTE(self) -> str:
        """Scrcpy远程路径"""
        return self.get_value("device.tools.scrcpy.remote", "/data/local/tmp/scrcpy-server-v1.20.jar")
        
    @property
    def ASSETS_FOLDER(self) -> str:
        """资源文件夹路径"""
        return self.get_value("app.assets.folder", "./assets")
        
    @property
    def ASSETS_MODULE(self) -> str:
        """资源模块路径"""
        return self.get_value("app.assets.module", "./tasks")
        
    @property
    def COLOR_SIMILAR_THRESHOLD(self) -> int:
        """颜色相似度阈值"""
        return self.get_value("app.params.color_similar_threshold", 10)
        
    @property
    def BUTTON_OFFSET(self) -> Tuple[int, int]:
        """按钮偏移量"""
        return self.get_value("app.params.button_offset", (20, 20))
        
    @property
    def BUTTON_MATCH_SIMILARITY(self) -> float:
        """按钮匹配相似度"""
        return self.get_value("app.params.button_match_similarity", 0.85)
        
    @property
    def WAIT_BEFORE_SAVING_SCREEN_SHOT(self) -> int:
        """保存截图前等待时间"""
        return self.get_value("app.params.wait_before_saving_screen_shot", 1) 