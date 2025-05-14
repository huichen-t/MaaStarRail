"""
Alas安装程序。
负责自动化安装和配置Alas所需的所有组件。
包括：
- Git安装和配置
- Python包安装
- ADB工具安装
- 应用更新
- 环境检查
"""

from deploy.Windows.logger import Progress, logger
from deploy.Windows.patch import pre_checks

# 执行预检查，确保环境满足安装要求
pre_checks()

from deploy.Windows.adb import AdbManager
from deploy.Windows.alas import AlasManager
from deploy.Windows.app import AppManager
from deploy.Windows.config import ExecutionError
from deploy.Windows.git import GitManager
from deploy.Windows.pip import PipManager


class Installer(GitManager, PipManager, AdbManager, AppManager, AlasManager):
    """
    安装器类。
    继承自多个管理器类，提供完整的安装功能。
    
    功能：
    - Git安装和配置
    - Python包管理
    - ADB工具安装
    - 应用管理
    - Alas程序管理
    """
    
    def install(self):
        """
        执行安装流程。
        按顺序执行以下步骤：
        1. 清理旧的配置
        2. 安装Git
        3. 关闭已运行的Alas
        4. 安装Python依赖
        5. 更新应用
        6. 安装ADB
        
        如果任何步骤失败，将抛出ExecutionError异常。
        """
        from deploy.Windows.atomic import atomic_failure_cleanup
        # 清理旧的配置，确保安装环境干净
        atomic_failure_cleanup('./config')
        try:
            # 按顺序执行安装步骤
            self.git_install()      # 安装Git
            self.alas_kill()        # 关闭已运行的Alas
            self.pip_install()      # 安装Python依赖
            self.app_update()       # 更新应用
            self.adb_install()      # 安装ADB
        except ExecutionError:
            # 如果安装失败，退出程序
            exit(1)


def run():
    """
    运行安装程序的主函数。
    显示进度条并执行安装流程。
    """
    # 开始显示进度条
    Progress.Start()
    # 创建安装器实例
    installer = Installer()
    # 显示部署配置信息
    Progress.ShowDeployConfig()

    # 执行安装
    installer.install()

    # 安装完成
    logger.info('Finish')
    # 结束进度条显示
    Progress.Finish()
