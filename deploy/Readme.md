# Deploy 部署目录

本目录包含Alas的部署和安装相关文件，用于自动化安装和配置Alas所需的所有组件。

## 目录结构

```
Deploy/
├── Windows/              # Windows平台特定的部署文件
├── git_over_cdn/        # Git CDN相关配置
├── installer.py         # 主安装程序
├── set.py              # 设置相关脚本
└── Readme.md           # 本说明文档
```

## 主要功能

### 1. 安装功能
- 自动化安装和配置Alas所需的所有组件
- 包括Git、Python包、ADB工具等
- 提供环境检查和预配置

### 2. 启动器功能
- 提供`Alas.exe`启动器
- 支持从`.bat`文件转换的`.exe`启动方式
- 提供备选的`.bat`启动方式

### 3. 组件管理
- Git管理：安装和配置Git
- Pip管理：Python包依赖管理
- ADB管理：Android调试工具管理
- 应用管理：Alas应用更新
- Alas管理：程序运行状态管理

## 安装流程

1. 环境预检查
   - 检查系统环境
   - 验证必要组件

2. 安装步骤
   - 清理旧配置
   - 安装Git
   - 关闭已运行的Alas
   - 安装Python依赖
   - 更新应用
   - 安装ADB

## 使用方法

### 安装Alas
在Alas根目录下运行：
```bash
python -m deploy.installer
```

### 启动器说明
- 主启动器：`Alas.exe`
- 备选启动器：`deploy/launcher/Alas.bat`

注意：如果杀毒软件对`Alas.exe`报警，可以使用`Alas.bat`替代，功能相同。

## 注意事项

1. 安装前请确保：
   - 系统满足最低要求
   - 有足够的磁盘空间
   - 有管理员权限

2. 安装过程中：
   - 不要关闭命令行窗口
   - 保持网络连接
   - 等待所有步骤完成

3. 如果安装失败：
   - 检查错误日志
   - 确保网络连接正常
   - 尝试重新运行安装程序

## 常见问题

1. 杀毒软件报警
   - 使用`Alas.bat`替代`Alas.exe`
   - 将程序添加到杀毒软件白名单

2. 安装失败
   - 检查网络连接
   - 确保有管理员权限
   - 查看错误日志

3. 启动器问题
   - 尝试使用备选启动器
   - 检查文件权限
   - 确保Python环境正确

## 技术支持

如果遇到问题，请：
1. 查看错误日志
2. 检查常见问题解答
3. 在项目Issues中提交问题

# Launcher

Launcher `Alas.exe` is a `.bat` file converted to `.exe` file by [Bat To Exe Converter](https://f2ko.de/programme/bat-to-exe-converter/).

If you have warnings from your anti-virus software, replace `alas.exe` with `deploy/launcher/Alas.bat`. They should do the same thing.

