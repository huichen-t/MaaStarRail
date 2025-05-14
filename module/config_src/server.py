"""
服务器配置模块，用于管理不同服务器和语言设置。
使用 'import module.config_src.server as server' 导入，不要使用 'from xxx import xxx'。
"""

# 默认语言设置为中文，避免使用开发工具时出错
lang = 'cn'
# 默认服务器设置为国服官方
server = 'CN-Official'

# 支持的语言列表
VALID_LANG = ['cn', 'en']

# 服务器名称到包名的映射
VALID_SERVER = {
    'CN-Official': 'com.miHoYo.hkrpg',      # 国服官方
    'CN-Bilibili': 'com.miHoYo.hkrpg.bilibili',  # 国服B站
    'OVERSEA-America': 'com.HoYoverse.hkrpgoversea',  # 美服
    'OVERSEA-Asia': 'com.HoYoverse.hkrpgoversea',     # 亚服
    'OVERSEA-Europe': 'com.HoYoverse.hkrpgoversea',   # 欧服
    'OVERSEA-TWHKMO': 'com.HoYoverse.hkrpgoversea',   # 台港澳服
}

# 所有有效的包名集合
VALID_PACKAGE = set(list(VALID_SERVER.values()))

# 云游戏服务器名称到包名的映射
VALID_CLOUD_SERVER = {
    'CN-Official': 'com.miHoYo.cloudgames.hkrpg',  # 国服官方云游戏
}

# 所有有效的云游戏包名集合
VALID_CLOUD_PACKAGE = set(list(VALID_CLOUD_SERVER.values()))

# 包名到启动Activity的映射
DICT_PACKAGE_TO_ACTIVITY = {
    'com.miHoYo.hkrpg': 'com.mihoyo.combosdk.ComboSDKActivity',  # 国服官方
    'com.miHoYo.hkrpg.bilibili': 'com.mihoyo.combosdk.ComboSDKActivity',  # 国服B站
    'com.HoYoverse.hkrpgoversea': 'com.mihoyo.combosdk.ComboSDKActivity',  # 国际服
    'com.miHoYo.cloudgames.hkrpg': 'com.mihoyo.cloudgame.ui.SplashActivity',  # 云游戏
}


def set_lang(lang_: str):
    """
    更改语言设置，这将全局生效，
    包括资源文件和特定语言的方法。

    Args:
        lang_: 包名或服务器名称。
    """
    global lang
    lang = lang_

    # 释放资源以应用新的语言设置
    from module.base.resource import release_resources
    release_resources()


def to_server(package_or_server: str) -> str:
    """
    将包名或服务器名称转换为标准服务器名称。
    对于未知的包名，将其视为国服渠道服务器。

    Args:
        package_or_server: 包名或服务器名称

    Returns:
        str: 标准服务器名称

    Raises:
        ValueError: 当包名无效时抛出
    """
    # 无法区分不同地区的国际服，
    # 假设为'OVERSEA-Asia'
    if package_or_server == 'com.HoYoverse.hkrpgoversea':
        return 'OVERSEA-Asia'

    # 检查普通服务器
    for key, value in VALID_SERVER.items():
        if value == package_or_server:
            return key
        if key == package_or_server:
            return key
    # 检查云游戏服务器
    for key, value in VALID_CLOUD_SERVER.items():
        if value == package_or_server:
            return key
        if key == package_or_server:
            return key

    raise ValueError(f'包名无效: {package_or_server}')


def to_package(package_or_server: str, is_cloud=False) -> str:
    """
    将包名或服务器名称转换为标准包名。

    Args:
        package_or_server: 包名或服务器名称
        is_cloud: 是否为云游戏服务器

    Returns:
        str: 标准包名

    Raises:
        ValueError: 当服务器名称无效时抛出
    """
    if is_cloud:
        # 检查云游戏服务器
        for key, value in VALID_CLOUD_SERVER.items():
            if value == package_or_server:
                return value
            if key == package_or_server:
                return value
    else:
        # 检查普通服务器
        for key, value in VALID_SERVER.items():
            if value == package_or_server:
                return value
            if key == package_or_server:
                return value

    raise ValueError(f'服务器无效: {package_or_server}')
