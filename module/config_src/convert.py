"""
配置转换模块，用于处理游戏内各种名称和配置的转换。
主要处理副本名称、活动名称等在不同版本或场景下的映射关系。
"""

def convert_daily(value):
    """
    转换每日任务名称。
    将旧的任务名称转换为新的任务名称。

    Args:
        value (str): 原始任务名称

    Returns:
        str: 转换后的任务名称
    """
    if value == "Calyx_Crimson_Hunt":
        value = "Calyx_Crimson_The_Hunt"
    return value


def convert_20_dungeon(value):
    """
    转换20级副本名称。
    将基础副本名称转换为带区域信息的完整副本名称。

    Args:
        value (str): 原始副本名称

    Returns:
        str: 转换后的副本名称
    """
    # 金色回忆副本转换
    if value == 'Calyx_Golden_Memories':
        return 'Calyx_Golden_Memories_Jarilo_VI'
    if value == 'Calyx_Golden_Aether':
        return 'Calyx_Golden_Aether_Jarilo_VI'
    if value == 'Calyx_Golden_Treasures':
        return 'Calyx_Golden_Treasures_Jarilo_VI'
    if value == 'Calyx_Golden_Memories':
        return 'Calyx_Golden_Memories_Jarilo_VI'

    # 红色副本转换
    if value == 'Calyx_Crimson_Destruction':
        return 'Calyx_Crimson_Destruction_Herta_StorageZone'
    if value == 'Calyx_Crimson_The_Hunt':
        return 'Calyx_Crimson_The_Hunt_Jarilo_OutlyingSnowPlains'
    if value == 'Calyx_Crimson_Erudition':
        return 'Calyx_Crimson_Erudition_Jarilo_RivetTown'
    if value == 'Calyx_Crimson_Harmony':
        return 'Calyx_Crimson_Harmony_Jarilo_RobotSettlement'
    if value == 'Calyx_Crimson_Nihility':
        return 'Calyx_Crimson_Nihility_Jarilo_GreatMine'
    if value == 'Calyx_Crimson_Preservation':
        return 'Calyx_Crimson_Preservation_Herta_SupplyZone'
    if value == 'Calyx_Crimson_Abundance':
        return 'Calyx_Crimson_Abundance_Jarilo_BackwaterPass'

    return value


def convert_rogue_farm(value):
    """
    转换模拟宇宙进度值。
    将进度值转换为剩余值（100减去当前值）。

    Args:
        value (dict): 包含进度值的字典

    Returns:
        dict: 转换后的进度值字典
    """
    if isinstance(value, dict) and 'value' in value.keys():
        value['value'] = 100 - value['value']
        value['total'] = 100
        return value


def convert_Item_Moon_Madness_Fang(value):
    """
    转换月之狂怒獠牙物品名称。
    将旧物品名称转换为新物品名称。

    Args:
        value (dict): 包含物品信息的字典

    Returns:
        dict: 转换后的物品信息字典
    """
    if isinstance(value, dict):
        value['item'] = 'Moon_Rage_Fang'
    return value


def convert_31_dungeon(value):
    """
    转换31级副本名称。
    将特殊副本名称转换为标准副本名称。

    Args:
        value (str): 原始副本名称

    Returns:
        str: 转换后的副本名称
    """
    if value == 'Calyx_Crimson_Remembrance_Special_StrifeRuinsCastrumKremnos':
        return 'Calyx_Crimson_Remembrance_Amphoreus_StrifeRuinsCastrumKremnos'
    return value


def convert_32_weekly(value):
    """
    转换32级周常副本名称。
    将旧版本副本名称转换为新版本副本名称。

    Args:
        value (str): 原始副本名称

    Returns:
        str: 转换后的副本名称
    """
    if value == 'Echo_of_War_Borehole_Planet_Old_Crater':
        return 'Echo_of_War_Borehole_Planet_Past_Nightmares'
    return value
