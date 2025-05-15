# 设备管理系统设计文档

## 设计目标

1. 将设备管理功能分为工具类和全局管理类，确保功能清晰、职责单一
2. 使用单例模式统一管理设备连接，避免重复连接
3. 提供统一的设备操作接口，简化设备管理
4. 支持多种设备类型和连接方式
5. 实现资源的自动管理和释放

## 系统结构

```
module/device/
├── device_utils.py      # 设备工具类，提供静态方法
├── device_manager.py    # 设备管理器，全局单例
└── DEVICE_DESIGN.md     # 设计文档
```

## 功能分类

### 1. 设备工具类 (DeviceUtils)

#### 1.1 设备序列号处理
- `revise_serial`: 修正设备序列号格式
- `get_device_serial`: 获取设备序列号
- `is_valid_serial`: 验证序列号有效性

#### 1.2 设备类型识别
- `is_emulator`: 判断是否为模拟器
- `is_network_device`: 判断是否为网络设备
- `is_over_http`: 判断是否通过HTTP连接
- `get_device_type`: 获取设备类型
- `is_mumu_family`: 判断是否为MuMu系列模拟器

#### 1.3 端口处理
- `extract_port`: 从序列号中提取端口号
- `get_common_ports`: 获取常用端口列表

### 2. 设备管理器 (DeviceManager)

#### 2.1 设备连接管理
- `connect_device`: 连接指定设备
- `disconnect_device`: 断开当前设备连接
- `_init_connection`: 初始化设备连接

#### 2.2 设备操作接口
- `adb`: 获取ADB设备对象
- `u2`: 获取uiautomator2设备对象
- `adb_binary`: 获取ADB可执行文件路径
- `adb_client`: 获取ADB客户端对象

#### 2.3 端口转发管理
- `adb_forward`: 设置端口转发
- `adb_reverse`: 设置反向端口转发
- `adb_forward_remove`: 移除端口转发
- `adb_reverse_remove`: 移除反向端口转发

#### 2.4 包管理
- `list_package`: 获取设备上所有已安装的包
- `list_known_packages`: 获取已知的包列表
- `detect_package`: 检测设备上所有可能的包
- `install_uiautomator2`: 初始化uiautomator2
- `uninstall_minicap`: 卸载minicap
- `restart_atx`: 重启ATX

#### 2.5 资源管理
- `add_resource`: 添加需要管理的资源
- `release_resources`: 释放所有资源

#### 2.6 设备信息
- `get_device_info`: 获取设备信息
- `serial`: 获取当前设备序列号

#### 2.7 设备监控
- `get_device_status`: 获取设备状态信息
- `is_device_healthy`: 检查设备是否健康

#### 2.8 应用控制
- `package`: 获取/设置当前目标应用包名
- `app_current`: 获取当前运行的应用包名
- `app_is_running`: 检查目标应用是否正在运行
- `app_start`: 启动目标应用
- `app_stop`: 停止目标应用

#### 2.9 界面操作
- `hierarchy_timer_set`: 设置界面层级获取的时间间隔
- `dump_hierarchy`: 获取当前界面的层级结构
- `xpath_to_button`: 将xpath路径转换为可点击的按钮对象

### 3. 设备监控器 (DeviceMonitor)

#### 3.1 监控管理
- `start`: 启动设备监控
- `stop`: 停止设备监控
- `get_status`: 获取设备状态
- `is_healthy`: 检查设备健康状态

#### 3.2 状态监控
- 连接状态监控
  - ADB连接状态
  - uiautomator2连接状态
  - 网络连接状态
- 性能指标监控
  - CPU使用率
  - 内存使用率
  - 电池电量
  - 电池温度
- 健康检查
  - CPU使用率阈值（90%）
  - 内存使用率阈值（90%）
  - 电池电量阈值（10%）
  - 电池温度阈值（45℃）

## 实现方式

### 1. 设备工具类

```python
class DeviceUtils:
    @staticmethod
    def revise_serial(serial: str) -> str:
        """修正设备序列号格式"""
        pass

    @staticmethod
    def is_valid_serial(serial: str) -> bool:
        """验证序列号有效性"""
        pass

    @staticmethod
    def is_emulator(serial: str) -> bool:
        """判断是否为模拟器"""
        pass
```

### 2. 设备管理器

```python
class DeviceManager:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def connect_device(self, serial: str) -> 'DeviceManager':
        """连接指定设备"""
        pass
    
    @cached_property
    def adb(self) -> AdbDevice:
        """获取ADB设备对象"""
        pass
    
    @cached_property
    def u2(self) -> u2.Device:
        """获取uiautomator2设备对象"""
        pass
```

### 3. 设备监控器

```python
class DeviceMonitor:
    def __init__(self, device_manager: 'DeviceManager'):
        self.device_manager = device_manager
        self._stop_event = Event()
        self._monitor_thread: Optional[Thread] = None
        self._check_interval = 5  # 检查间隔（秒）
        self._status = {
            'connected': False,
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'battery_level': 0,
            'battery_temperature': 0,
            'network_status': 'unknown',
            'adb_status': 'unknown',
            'u2_status': 'unknown'
        }
    
    def start(self) -> None:
        """启动监控"""
        pass
    
    def stop(self) -> None:
        """停止监控"""
        pass
    
    def _monitor_loop(self) -> None:
        """监控循环"""
        pass
    
    def _check_device_status(self) -> None:
        """检查设备状态"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """获取设备状态"""
        pass
    
    def is_healthy(self) -> bool:
        """检查设备是否健康"""
        pass
```

## 使用示例

### 1. 连接设备

```python
from module.device.device_manager import device_manager

# 连接设备
device_manager.connect_device("emulator-5554")

# 获取设备信息
info = device_manager.get_device_info()
print(f"设备类型: {info['device_type']}")
print(f"是否为模拟器: {info['is_emulator']}")
```

### 2. 执行ADB命令

```python
# 获取包列表
packages = device_manager.list_package()

# 设置端口转发
port = device_manager.adb_forward("tcp:7912")

# 执行shell命令
result = device_manager.adb.shell("pm list packages")
```

### 3. 使用uiautomator2

```python
# 初始化uiautomator2
device_manager.install_uiautomator2()

# 使用uiautomator2操作设备
device = device_manager.u2
device.app_start("com.example.app")
device.click(100, 200)
```

### 4. 包管理

```python
# 检测包
package = device_manager.detect_package()

# 重启ATX
device_manager.restart_atx()
```

### 5. 设备监控

```python
# 获取设备状态
status = device_manager.get_device_status()
print(f"CPU使用率: {status['cpu_usage']}%")
print(f"内存使用率: {status['memory_usage']}%")
print(f"电池电量: {status['battery_level']}%")
print(f"电池温度: {status['battery_temperature']}℃")
print(f"网络状态: {status['network_status']}")
print(f"ADB状态: {status['adb_status']}")
print(f"uiautomator2状态: {status['u2_status']}")

# 检查设备健康状态
if device_manager.is_device_healthy():
    print("设备状态正常")
else:
    print("设备状态异常，请检查")
```

## 注意事项

1. 设备连接管理
   - 使用单例模式确保全局只有一个设备管理器实例
   - 连接新设备前会自动断开当前设备
   - 断开连接时会自动释放所有资源

2. 错误处理
   - 所有设备操作都有适当的错误处理
   - 连接失败时会抛出异常并提供详细信息
   - 资源释放失败会记录日志但不会中断程序

3. 资源管理
   - 使用 `add_resource` 添加需要管理的资源
   - 断开连接时自动释放所有资源
   - 支持 `release` 和 `close` 两种资源释放方式

4. 性能优化
   - 使用 `cached_property` 缓存设备对象
   - 优先使用快速的命令获取包列表
   - 重用现有的端口转发

5. 配置管理
   - 包名列表和云游戏标志需要从配置中获取
   - 支持自动检测和设置包名
   - 支持云游戏和普通游戏的区分

6. 设备监控
   - 监控线程作为守护线程运行
   - 定期检查设备状态（默认5秒）
   - 自动处理监控异常
   - 提供健康状态检查
   - 支持手动启动和停止监控

## 后续优化方向

1. 配置集成
   - 实现配置管理器的集成
   - 添加配置更新功能
   - 支持动态配置更新

2. 错误处理增强
   - 添加重试机制
   - 实现更详细的错误分类
   - 提供错误恢复建议

3. 性能优化
   - 优化包检测逻辑
   - 改进资源管理机制
   - 添加连接池支持

4. 功能扩展
   - 添加设备状态监控
   - 实现设备自动重连
   - 支持多设备并行操作

5. 监控增强
   - 添加更多性能指标监控
   - 实现监控数据持久化
   - 添加监控告警机制
   - 支持自定义监控阈值
   - 提供监控数据可视化 