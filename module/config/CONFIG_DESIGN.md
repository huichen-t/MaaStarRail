# 配置系统设计文档

## 1. 设计目标

将配置系统分为平台配置和游戏配置两大部分，实现配置的清晰分离和统一管理。通过配置管理器提供全局访问接口，确保配置的一致性和易用性。

## 2. 系统结构

```
module/config/
├── __init__.py
├── base_config.py       # 配置基类
├── platform_config.py   # 平台相关配置
├── game_config.py      # 游戏相关配置
├── config_manager.py   # 配置管理器
├── config_demo.py      # 配置使用演示
└── CONFIG_DESIGN.md    # 本文档
```

## 3. 配置分类

### 3.1 平台配置 (platform_config.py)

1. 设备配置
   - 设备通信参数
     * DEVICE_OVER_HTTP: 是否使用HTTP通信
     * FORWARD_PORT_RANGE: 端口转发范围
     * REVERSE_SERVER_PORT: 反向服务器端口
   - 设备工具路径
     * MINITOUCH_FILEPATH_REMOTE: minitouch远程路径
     * MAATOUCH_FILEPATH_LOCAL: maatouch本地路径
     * MAATOUCH_FILEPATH_REMOTE: maatouch远程路径
     * ASCREENCAP_FILEPATH_LOCAL: ascreencap本地路径
     * ASCREENCAP_FILEPATH_REMOTE: ascreencap远程路径
   - DroidCast配置
     * DROIDCAST_VERSION: DroidCast版本
     * DROIDCAST_FILEPATH_LOCAL: DroidCast本地路径
     * DROIDCAST_FILEPATH_REMOTE: DroidCast远程路径
     * DROIDCAST_RAW_FILEPATH_LOCAL: DroidCast Raw本地路径
     * DROIDCAST_RAW_FILEPATH_REMOTE: DroidCast Raw远程路径
   - Hermit配置
     * HERMIT_FILEPATH_LOCAL: Hermit本地路径
   - Scrcpy配置
     * SCRCPY_FILEPATH_LOCAL: Scrcpy本地路径
     * SCRCPY_FILEPATH_REMOTE: Scrcpy远程路径

2. 应用配置
   - 资源路径
     * ASSETS_FOLDER: 资源文件夹路径
     * ASSETS_MODULE: 资源模块路径
   - 基础参数
     * COLOR_SIMILAR_THRESHOLD: 颜色相似度阈值
     * BUTTON_OFFSET: 按钮偏移量
     * BUTTON_MATCH_SIMILARITY: 按钮匹配相似度
     * WAIT_BEFORE_SAVING_SCREEN_SHOT: 保存截图前等待时间

### 3.2 游戏配置 (game_config.py)

1. 游戏参数
   - 基础参数
     * WAIT_TIMEOUT: 等待超时时间
     * CLICK_INTERVAL: 点击间隔时间
     * SWIPE_DURATION: 滑动持续时间
     * DRAG_DURATION: 拖拽持续时间

2. 界面元素
   - 主菜单
     * name: 元素名称
     * template: 模板图片
     * position: 位置坐标
     * click_offset: 点击偏移量
   - 战斗界面
     * name: 元素名称
     * template: 模板图片
     * position: 位置坐标
     * click_offset: 点击偏移量

3. 任务配置
   - 日常任务
     * name: 任务名称
     * enabled: 是否启用
     * priority: 优先级
     * subtasks: 子任务列表
   - 周常任务
     * name: 任务名称
     * enabled: 是否启用
     * priority: 优先级
     * subtasks: 子任务列表

## 4. 实现方式

### 4.1 配置基类 (base_config.py)

```python
class BaseConfig:
    """配置基类，提供基础配置功能"""
    
    def __init__(self, config_name: str):
        """初始化配置"""
        self.config_name = config_name
        self.config_path = os.path.join("config", config_name)
        self._config = {}
        self.load()
    
    def load(self) -> None:
        """从配置文件加载配置"""
        pass
    
    def save(self) -> None:
        """保存配置到文件"""
        pass
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        pass
    
    def set_value(self, key: str, value: Any) -> None:
        """设置配置值"""
        pass
    
    def update(self, config_dict: Dict[str, Any]) -> None:
        """批量更新配置"""
        pass
```

### 4.2 配置管理器 (config_manager.py)

```python
class ConfigManager:
    """配置管理器类，使用单例模式管理所有配置实例"""
    
    _instance = None
    
    def __new__(cls) -> 'ConfigManager':
        """实现单例模式"""
        pass
    
    def __init__(self) -> None:
        """初始化配置管理器"""
        pass
    
    @property
    def platform(self) -> PlatformConfig:
        """获取平台配置实例"""
        pass
    
    @property
    def game(self) -> GameConfig:
        """获取游戏配置实例"""
        pass
    
    def reload_all(self) -> None:
        """重新加载所有配置"""
        pass
    
    def save_all(self) -> None:
        """保存所有配置"""
        pass
```

## 5. 使用方式

### 5.1 基本使用

```python
from module.config.config_manager import config_manager

# 获取平台配置
platform_config = config_manager.platform
device_resolution = platform_config.DEVICE_RESOLUTION
assets_folder = platform_config.ASSETS_FOLDER

# 获取游戏配置
game_config = config_manager.game
wait_timeout = game_config.WAIT_TIMEOUT
click_interval = game_config.CLICK_INTERVAL
```

### 5.2 配置更新

```python
# 更新单个配置项
platform_config.set_value("device.resolution", (1920, 1080))

# 批量更新配置
platform_config.update({
    "device": {
        "over_http": True,
        "forward_port_range": (30000, 31000)
    }
})

# 更新任务配置
game_config.update_task_config("daily", {
    "name": "日常任务",
    "enabled": False,
    "priority": 3,
    "subtasks": ["login", "claim_rewards"]
})
```

### 5.3 配置管理

```python
# 重新加载所有配置
config_manager.reload_all()

# 保存所有配置
config_manager.save_all()
```

## 6. 注意事项

1. 配置访问
   - 通过配置管理器访问配置实例
   - 使用属性访问器获取配置值
   - 避免直接修改配置文件

2. 配置更新
   - 使用 set_value 更新单个配置项
   - 使用 update 批量更新配置
   - 更新后会自动保存到文件

3. 错误处理
   - 配置加载失败时创建默认配置
   - 使用日志记录配置操作
   - 异常传播确保错误可追踪

4. 文件管理
   - 配置文件保存在 config 目录下
   - 使用 JSON 格式存储配置
   - 支持 UTF-8 编码 