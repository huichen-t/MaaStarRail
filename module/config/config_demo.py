"""
配置系统演示脚本。
展示如何使用配置管理器访问和修改配置。
"""

from module.config.config_manager import config_manager
from module.base.logger import logger


def demo_platform_config():
    """演示平台配置的使用"""
    logger.info("=== 平台配置演示 ===")
    
    # 获取平台配置实例
    platform = config_manager.platform
    
    # 读取配置
    logger.info(f"设备分辨率: {platform.DEVICE_RESOLUTION}")
    logger.info(f"是否使用HTTP通信: {platform.DEVICE_OVER_HTTP}")
    logger.info(f"资源文件夹路径: {platform.ASSETS_FOLDER}")
    
    # 修改配置
    logger.info("\n修改配置示例:")
    platform.set_value("device.resolution", (1920, 1080))
    logger.info(f"新的设备分辨率: {platform.DEVICE_RESOLUTION}")
    
    # 批量更新配置
    logger.info("\n批量更新配置示例:")
    platform.update({
        "device": {
            "over_http": True,
            "forward_port_range": (30000, 31000)
        }
    })
    logger.info(f"新的HTTP通信设置: {platform.DEVICE_OVER_HTTP}")
    logger.info(f"新的端口范围: {platform.FORWARD_PORT_RANGE}")


def demo_game_config():
    """演示游戏配置的使用"""
    logger.info("\n=== 游戏配置演示 ===")
    
    # 获取游戏配置实例
    game = config_manager.game
    
    # 读取配置
    logger.info(f"等待超时时间: {game.WAIT_TIMEOUT}秒")
    logger.info(f"点击间隔: {game.CLICK_INTERVAL}秒")
    
    # 获取界面元素配置
    main_menu = game.get_ui_element("main_menu")
    logger.info(f"主菜单配置: {main_menu}")
    
    # 获取任务配置
    daily_task = game.get_task_config("daily")
    logger.info(f"日常任务配置: {daily_task}")
    
    # 检查任务状态
    logger.info(f"日常任务是否启用: {game.is_task_enabled('daily')}")
    logger.info(f"日常任务优先级: {game.get_task_priority('daily')}")
    logger.info(f"日常任务子任务: {game.get_task_subtasks('daily')}")
    
    # 修改任务配置
    logger.info("\n修改任务配置示例:")
    game.update_task_config("daily", {
        "name": "日常任务",
        "enabled": False,
        "priority": 3,
        "subtasks": ["login", "claim_rewards"]
    })
    logger.info(f"更新后的日常任务配置: {game.get_task_config('daily')}")


def main():
    """主函数"""
    try:
        # 演示平台配置
        demo_platform_config()
        
        # 演示游戏配置
        demo_game_config()
        
        # 重新加载所有配置
        logger.info("\n=== 重新加载所有配置 ===")
        config_manager.reload_all()
        
        # 保存所有配置
        logger.info("\n=== 保存所有配置 ===")
        config_manager.save_all()
        
    except Exception as e:
        logger.error(f"演示过程中发生错误: {str(e)}")
        raise


if __name__ == "__main__":
    main() 