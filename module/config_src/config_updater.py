"""
配置更新器模块，提供配置的生成、更新和管理功能。
主要功能包括：
1. 配置文件的生成和管理
2. 配置数据的处理和转换
3. 配置的国际化支持
4. 配置模板的生成
"""

import re
import typing as t
from copy import deepcopy

from cached_property import cached_property

# from deploy.Windows.utils import DEPLOY_TEMPLATE, poor_yaml_read, poor_yaml_write
from module.base.timer import timer
from module.config_src.convert import *
from module.config_src.deep import deep_default, deep_get, deep_iter, deep_set
from module.config_src.server import VALID_SERVER
from module.config_src.utils import *

# 配置导入模板
CONFIG_IMPORT = '''
import datetime

# 此文件由 module/config_src/config_updater.py 自动生成。
# 请勿手动修改。


class GeneratedConfig:
    """
    自动生成的配置类
    """
'''.strip().split('\n')

# GUI语言到游戏内语言的映射
DICT_GUI_TO_INGAME = {
    'zh-CN': 'cn',  # 简体中文
    'en-US': 'en',  # 英文
    'ja-JP': 'jp',  # 日文
    'zh-TW': 'cht', # 繁体中文
    'es-ES': 'es',  # 西班牙文
}


def gui_lang_to_ingame_lang(lang: str) -> str:
    """
    将GUI语言代码转换为游戏内语言代码。

    Args:
        lang (str): GUI语言代码，如'zh-CN'

    Returns:
        str: 游戏内语言代码，如'cn'
    """
    return DICT_GUI_TO_INGAME.get(lang, 'en')


def get_generator():
    """
    获取代码生成器实例。

    Returns:
        CodeGenerator: 代码生成器实例
    """
    from module.base.code_generator import CodeGenerator
    return CodeGenerator()


class ConfigGenerator:
    """
    配置生成器类，用于生成和管理项目的配置系统。
    
    主要功能：
    1. 配置文件的生成和管理
       - 从多个YAML文件生成统一的配置
       - 生成Python代码形式的配置
       - 生成国际化(i18n)文件
       - 生成部署模板
    
    2. 配置数据处理
       - 合并多个配置源（task.yaml, argument.yaml, override.yaml, default.yaml）
       - 处理配置项的类型转换和验证
       - 管理配置项的默认值和选项
    
    3. 特殊功能
       - 生成存储类（StoredGenerated）
       - 生成菜单定义
       - 处理角色模板检查
       - 生成部署配置模板
    
    工作流程：
    1. 读取基础配置文件
    2. 合并和标准化配置数据
    3. 生成Python代码
    4. 生成国际化文件
    5. 生成部署模板
    """

    @cached_property
    def argument(self):
        """
        加载argument.yaml并标准化其结构。

        配置结构：
        <group>:
            <argument>:
                type: checkbox|select|textarea|input  # 参数类型
                value:  # 参数值
                option (Optional):  # 选项列表（如果有）
                validate (Optional): datetime  # 验证规则

        Returns:
            dict: 标准化的参数配置
        """
        data = {}
        raw = read_file(filepath_argument('argument'))

        def option_add(keys, options):
            """
            添加选项到指定路径。

            Args:
                keys (list): 配置路径
                options (list): 要添加的选项列表
            """
            options = deep_get(raw, keys=keys, default=[]) + options
            deep_set(raw, keys=keys, value=options)

        # 插入包名选项
        option_add(keys='Emulator.PackageName.option', options=list(VALID_SERVER.keys()))
        
        # 插入副本选项
        from tasks.dungeon.keywords import DungeonList
        # 获取金色回忆副本
        calyx_golden = [dungeon.name for dungeon in DungeonList.instances.values() if dungeon.is_Calyx_Golden_Memories]
        calyx_golden += [dungeon.name for dungeon in DungeonList.instances.values() if dungeon.is_Calyx_Golden_Aether]
        calyx_golden += [dungeon.name for dungeon in DungeonList.instances.values() if dungeon.is_Calyx_Golden_Treasures]
        
        # 获取深红副本
        from tasks.rogue.keywords import KEYWORDS_ROGUE_PATH as Path
        order = [Path.Destruction, Path.Preservation, Path.The_Hunt, Path.Abundance,
                 Path.Erudition, Path.Harmony, Path.Nihility, Path.Remembrance]
        calyx_crimson = []
        for path in order:
            calyx_crimson += [dungeon.name for dungeon in DungeonList.instances.values()
                              if dungeon.Calyx_Crimson_Path == path]
        
        # 获取停滞阴影副本
        from tasks.character.keywords import CombatType
        stagnant_shadow = []
        for type_ in CombatType.instances.values():
            stagnant_shadow += [dungeon.name for dungeon in DungeonList.instances.values()
                                if dungeon.Stagnant_Shadow_Combat_Type == type_]
        
        # 获取腐蚀洞穴副本
        cavern_of_corrosion = [dungeon.name for dungeon in DungeonList.instances.values() if
                               dungeon.is_Cavern_of_Corrosion]
        
        # 添加副本选项
        option_add(
            keys='Dungeon.Name.option',
            options=cavern_of_corrosion + calyx_golden + calyx_crimson + stagnant_shadow
        )
        
        # 添加双倍事件选项
        option_add(keys='Dungeon.NameAtDoubleCalyx.option', options=calyx_golden + calyx_crimson)
        option_add(keys='Dungeon.NameAtDoubleRelic.option', options=cavern_of_corrosion)
        option_add(
            keys='Weekly.Name.option',
            options=[dungeon.name for dungeon in DungeonList.instances.values() if dungeon.is_Echo_of_War])
        
        # 添加饰品提取选项
        ornament = [dungeon.name for dungeon in DungeonList.instances.values() if dungeon.is_Ornament_Extraction]
        option_add(keys='Ornament.Dungeon.option', options=ornament)
        
        # 添加角色选项
        from tasks.character.aired_version import list_support_characters
        unsupported_characters = []
        characters = [character.name for character in list_support_characters()
                      if character.name not in unsupported_characters]
        option_add(keys='DungeonSupport.Character.option', options=characters)
        
        # 添加委托选项
        from tasks.assignment.keywords import AssignmentEntry
        assignments = [entry.name for entry in AssignmentEntry.instances.values()]
        for i in range(4):
            option_add(keys=f'Assignment.Name_{i + 1}.option', options=assignments)
        
        # 添加规划器物品选项
        from tasks.planner.keywords.classes import ItemBase
        for item in ItemBase.instances.values():
            if item.is_ItemValuable:
                continue
            base = item.group_base
            deep_set(raw, keys=['Planner', f'Item_{base.name}'], value={
                'stored': 'StoredPlanner',
                'display': 'display',
                'type': 'planner',
            })

        # 加载配置
        for path, value in deep_iter(raw, depth=2):
            arg = {
                'type': 'input',
                'value': '',
                # option
            }
            if not isinstance(value, dict):
                value = {'value': value}
            arg['type'] = data_to_type(value, arg=path[1])
            if arg['type'] in ['stored', 'planner']:
                value['value'] = {}
                arg['display'] = 'hide'  # 默认隐藏stored类型
            if isinstance(value['value'], datetime):
                arg['type'] = 'datetime'
                arg['validate'] = 'datetime'
            # 手动定义具有最高优先级
            arg.update(value)
            deep_set(data, keys=path, value=arg)

        return data

    @cached_property
    def task(self):
        """
        读取并返回 task.yaml 文件内容。
        
        返回结构：
        <task_group>:
            <task>:
                <group>:
        
        Returns:
            dict: 任务分组及其详细内容
        """
        return read_file(filepath_argument('task'))

    @cached_property
    def default(self):
        """
        读取并返回 default.yaml 文件内容。
        
        返回结构：
        <task>:
            <group>:
                <argument>: value
        
        Returns:
            dict: 各任务的默认参数值
        """
        return read_file(filepath_argument('default'))

    @cached_property
    def override(self):
        """
        读取并返回 override.yaml 文件内容。
        
        返回结构：
        <task>:
            <group>:
                <argument>: value
        
        Returns:
            dict: 各任务的覆盖参数值
        """
        return read_file(filepath_argument('override'))

    @cached_property
    def gui(self):
        """
        读取并返回 gui.yaml 文件内容。
        
        返回结构：
        <i18n_group>:
            <i18n_key>: value, value is None
        
        Returns:
            dict: GUI 国际化相关内容
        """
        return read_file(filepath_argument('gui'))

    @cached_property
    @timer
    def args(self) -> dict:
        """
        合并各类配置定义，生成标准化的 args.json。
        
        合并流程：
            task.yaml ---+      # 任务定义文件，包含任务分组和任务列表
        argument.yaml ---+-----> args.json  # 参数定义文件，包含参数类型和默认值
        override.yaml ---+      # 参数覆盖文件，用于强制设置某些参数
        default.yaml ---+      # 默认值文件，设置参数的默认值
        
        Returns:
            dict: 标准化后的参数配置，包含所有任务、分组、参数的详细定义
            
        Raises:
            ValueError: 当配置合并过程中出现错误时抛出
        """
        # 初始化空字典存储最终配置
        data: dict = {}
        
        # 遍历任务配置，深度为3（task_group -> task -> group）
        for path, groups in deep_iter(self.task, depth=3):
            # 只处理tasks下的配置
            if 'tasks' not in path:
                continue
            task = path[2]  # 获取任务名称
            
            # 遍历任务下的所有分组
            for group in groups:
                # 检查分组是否在参数定义中存在
                if group not in self.argument:
                    print(f'警告: `{task}.{group}` 未关联到任何参数组')
                    continue
                try:
                    # 将参数定义复制到对应任务和分组下
                    deep_set(data, keys=[task, group], value=deepcopy(self.argument[group]))
                except Exception as e:
                    print(f'错误: 设置参数 `{task}.{group}` 时出错: {str(e)}')
                    continue

        def check_override(path: list, value: any) -> bool:
            """
            检查参数覆盖是否有效
            
            Args:
                path: 参数路径
                value: 要覆盖的值
                
            Returns:
                bool: 是否可以覆盖
                
            Raises:
                ValueError: 当参数验证失败时抛出
            """
            try:
                # 检查参数是否存在
                old = deep_get(data, keys=path, default=None)
                if old is None:
                    print(f'警告: `{".".join(path)}` 不是有效的参数')
                    return False
                    
                # 获取旧值和新值
                old_value = old.get('value', None) if isinstance(old, dict) else old
                value = old.get('value', None) if isinstance(value, dict) else value
                
                # 检查类型是否匹配
                # 允许Interval类型不同
                if type(value) != type(old_value) \
                        and old_value is not None \
                        and path[2] not in ['SuccessInterval', 'FailureInterval']:
                    print(
                        f'警告: `{value}` ({type(value)}) 和 `{".".join(path)}` ({type(old_value)}) 类型不匹配')
                    return False
                    
                # 检查值是否在选项列表中
                if isinstance(old, dict) and 'option' in old:
                    if value not in old['option']:
                        print(f'警告: `{value}` 不是参数 `{".".join(path)}` 的有效选项')
                        return False
                return True
            except Exception as e:
                print(f'错误: 验证参数 `{".".join(path)}` 时出错: {str(e)}')
                return False

        # 设置默认值
        for p, v in deep_iter(self.default, depth=3):
            if not check_override(p, v):
                continue
            try:
                deep_set(data, keys=p + ['value'], value=v)
            except Exception as e:
                print(f'错误: 设置默认值 `{".".join(p)}` 时出错: {str(e)}')
                continue
            
        # 覆盖不可修改的参数
        for p, v in deep_iter(self.override, depth=3):
            if not check_override(p, v):
                continue
            try:
                if isinstance(v, dict):
                    typ = v.get('type')
                    if typ == 'state':
                        pass  # 状态类型参数保持原样
                    elif typ == 'lock':
                        # 锁定类型参数设置为禁用显示
                        deep_default(v, keys='display', value="disabled")
                    elif deep_get(v, keys='value') is not None:
                        # 有值的参数隐藏显示
                        deep_default(v, keys='display', value='hide')
                    # 更新参数的所有属性
                    for arg_k, arg_v in v.items():
                        deep_set(data, keys=p + [arg_k], value=arg_v)
                else:
                    # 非字典类型的值直接设置
                    deep_set(data, keys=p + ['value'], value=v)
                    deep_set(data, keys=p + ['display'], value='hide')
            except Exception as e:
                print(f'错误: 覆盖参数 `{".".join(p)}` 时出错: {str(e)}')
                continue
            
        # 设置命令
        for path, groups in deep_iter(self.task, depth=3):
            if 'tasks' not in path:
                continue
            task = path[2]
            try:
                # 如果存在调度器命令，设置为任务名称并隐藏
                if deep_get(data, keys=f'{task}.Scheduler.Command'):
                    deep_set(data, keys=f'{task}.Scheduler.Command.value', value=task)
                    deep_set(data, keys=f'{task}.Scheduler.Command.display', value='hide')
            except Exception as e:
                print(f'错误: 设置命令 `{task}` 时出错: {str(e)}')
                continue

        return data

    @timer
    def generate_code(self):
        """
        生成 Python 代码形式的配置文件。
        
        输入：args.json
        输出：config_generated.py
        
        该方法会遍历所有参数分组和参数，将其以类属性的形式写入自动生成的 Python 文件，便于后续直接 import 使用。
        """
        visited_group = set()
        visited_path = set()
        lines = CONFIG_IMPORT
        for path, data in deep_iter(self.argument, depth=2):
            group, arg = path
            if group not in visited_group:
                lines.append('')
                lines.append(f'    # Group `{group}`')
                visited_group.add(group)

            option = ''
            if 'option' in data and data['option']:
                option = '  # ' + ', '.join([str(opt) for opt in data['option']])
            path = '.'.join(path)
            lines.append(f'    {path_to_arg(path)} = {repr(parse_value(data["value"], data=data))}{option}')
            visited_path.add(path)

        with open(filepath_code(), 'w', encoding='utf-8', newline='') as f:
            for text in lines:
                f.write(text + '\n')

    @timer
    def generate_stored(self):
        """
        生成存储类（StoredGenerated），用于管理所有 stored 类型的参数。
        
        该方法会自动收集所有 stored/planner 类型的参数，并为其生成对应的存储类属性。
        输出文件：module/config_src/stored/stored_generated.py
        """
        import module.config_src.stored.classes as classes
        gen = get_generator()
        gen.add('from module.config_src.stored.classes import (')
        with gen.tab():
            for cls in sorted([name for name in dir(classes) if name.startswith('Stored')]):
                gen.add(cls + ',')
        gen.add(')')
        gen.Empty()
        gen.Empty()
        gen.Empty()
        gen.CommentAutoGenerage('module/config_src/config_updater.py')

        with gen.Class('StoredGenerated'):
            for path, data in deep_iter(self.args, depth=3):
                cls = data.get('stored')
                if cls:
                    gen.add(f'{path[-1]} = {cls}("{".".join(path)}")')

        gen.write('module/config_src/stored/stored_generated.py')

    @cached_property
    def relics_nickname(self):
        """
        读取并返回遗器昵称映射表。
        
        Returns:
            dict: 遗器昵称与副本ID的映射关系
        """
        return read_file('tasks/relics/keywords/relicset_nickname.json')

    @timer
    def generate_i18n(self, lang):
        """
        生成指定语言的国际化(i18n)文件。
        
        输入：args.json、旧版 i18n/<lang>.json
        输出：i18n/<lang>.json
        
        该方法会遍历所有参数、任务、选项等，生成对应的多语言翻译内容，并自动补全缺失项。
        Args:
            lang (str): 目标语言代码，如 'zh-CN', 'en', 'jp' 等
        """
        new = {}
        old = read_file(filepath_i18n(lang))

        def deep_load(keys, default=True, words=('name', 'help')):
            for word in words:
                k = keys + [str(word)]
                d = ".".join(k) if default else str(word)
                v = deep_get(old, keys=k, default=d)
                deep_set(new, keys=k, value=v)

        # Menu
        for path, data in deep_iter(self.task, depth=3):
            if 'tasks' not in path:
                continue
            task_group, _, task = path
            deep_load(['Menu', task_group])
            deep_load(['Task', task])
        # Arguments
        visited_group = set()
        for path, data in deep_iter(self.argument, depth=2):
            if path[0] not in visited_group:
                deep_load([path[0], '_info'])
                visited_group.add(path[0])
            deep_load(path)
            if 'option' in data:
                deep_load(path, words=data['option'], default=False)

        # Package names
        # for package, server in VALID_PACKAGE.items():
        #     path = ['Emulator', 'PackageName', package]
        #     if deep_get(new, keys=path) == package:
        #         deep_set(new, keys=path, value=server.upper())
        # for package, server_and_channel in VALID_CHANNEL_PACKAGE.items():
        #     server, channel = server_and_channel
        #     name = deep_get(new, keys=['Emulator', 'PackageName', to_package(server)])
        #     if lang == SERVER_TO_LANG[server]:
        #         value = f'{name} {channel}渠道服 {package}'
        #     else:
        #         value = f'{name} {package}'
        #     deep_set(new, keys=['Emulator', 'PackageName', package], value=value)
        # Game server names
        # for server, _list in VALID_SERVER_LIST.items():
        #     for index in range(len(_list)):
        #         path = ['Emulator', 'ServerName', f'{server}-{index}']
        #         prefix = server.split('_')[0].upper()
        #         prefix = '国服' if prefix == 'CN' else prefix
        #         deep_set(new, keys=path, value=f'[{prefix}] {_list[index]}')

        ingame_lang = gui_lang_to_ingame_lang(lang)
        dailies = deep_get(self.argument, keys='Dungeon.Name.option')
        # Dungeon names
        i18n_memories = {
            'cn': '材料：角色经验（{dungeon} {world}）',
            'cht': '材料：角色經驗（{dungeon} {world}）',
            'jp': '素材：役割経験（{dungeon} {world}）：',
            'en': 'Material: Character EXP ({dungeon}, {world})',
            'es': 'Material: EXP de personaje ({dungeon}, {world})',
        }
        i18n_aether = {
            'cn': '材料：武器经验（{dungeon} {world}）',
            'cht': '材料：武器經驗（{dungeon} {world}）',
            'jp': '素材：武器経験（{dungeon} {world}）',
            'en': 'Material: Light Cone EXP ({dungeon}, {world})',
            'es': 'Material: EXP de conos de luz ({dungeon}, {world})',
        }
        i18n_treasure = {
            'cn': '材料：信用点（{dungeon} {world}）',
            'cht': '材料：信用點（{dungeon} {world}）',
            'jp': '素材：クレジット（{dungeon} {world}）',
            'en': 'Material: Credit ({dungeon}, {world})',
            'es': 'Material: Créditos ({dungeon}, {world})',
        }
        i18n_crimson = {
            'cn': '行迹材料：{path}（{plane}）',
            'cht': '行跡材料：{path}（{plane}）',
            'jp': '軌跡素材：{path}（{plane}）',
            'en': 'Trace: {path} ({plane})',
            'es': 'Rastros: {path} ({plane})',
        }
        i18n_relic = {
            'cn': '遗器：{relic}（{dungeon}）',
            'cht': '遺器：{relic}（{dungeon}）',
            'jp': '遺器：{relic}（{dungeon}）',
            'en': 'Relics: {relic} ({dungeon})',
            'es': 'Artefactos: {relic} ({dungeon})',
        }
        i18n_ornament = {
            'cn': '饰品：{relic}（{dungeon}）',
            'cht': '飾品：{relic}（{dungeon}）',
            'jp': '飾品：{relic}（{dungeon}）',
            'en': 'Ornament: {relic} ({dungeon})',
            'es': 'Ornamentos: {relic} ({dungeon})',
        }

        from tasks.dungeon.keywords import DungeonList, DungeonDetailed
        def relicdungeon2name(dun: DungeonList):
            dungeon_id = dun.dungeon_id
            relic_list = []
            for name, row in self.relics_nickname.items():
                if row.get('dungeon_id') == dungeon_id:
                    relic_list.append(row.get(ingame_lang, ''))
            return ' & '.join(relic_list)

        for dungeon in DungeonList.instances.values():
            dungeon: DungeonList = dungeon
            dungeon_name = dungeon.__getattribute__(ingame_lang)
            dungeon_name = re.sub('[「」]', '', dungeon_name)
            if dungeon.world:
                world_name = re.sub('[「」]', '', dungeon.world.__getattribute__(ingame_lang))
            else:
                world_name = ''
            if dungeon.is_Calyx_Golden_Memories:
                deep_set(new, keys=['Dungeon', 'Name', dungeon.name],
                         value=i18n_memories[ingame_lang].format(dungeon=dungeon_name, world=world_name))
            if dungeon.is_Calyx_Golden_Aether:
                deep_set(new, keys=['Dungeon', 'Name', dungeon.name],
                         value=i18n_aether[ingame_lang].format(dungeon=dungeon_name, world=world_name))
            if dungeon.is_Calyx_Golden_Treasures:
                deep_set(new, keys=['Dungeon', 'Name', dungeon.name],
                         value=i18n_treasure[ingame_lang].format(dungeon=dungeon_name, world=world_name))
            if dungeon.is_Calyx_Crimson:
                plane = dungeon.plane.__getattribute__(ingame_lang)
                plane = re.sub('[「」"]', '', plane)
                path = dungeon.Calyx_Crimson_Path.__getattribute__(ingame_lang)
                deep_set(new, keys=['Dungeon', 'Name', dungeon.name],
                         value=i18n_crimson[ingame_lang].format(path=path, plane=plane))
            if dungeon.is_Cavern_of_Corrosion:
                value = relicdungeon2name(dungeon)
                value = i18n_relic[ingame_lang].format(dungeon=dungeon_name, relic=value)
                value = value.replace('Cavern of Corrosion: ', '')
                deep_set(new, keys=['Dungeon', 'Name', dungeon.name], value=value)
            if dungeon.is_Ornament_Extraction:
                value = relicdungeon2name(dungeon)
                value = i18n_ornament[ingame_lang].format(dungeon=dungeon_name, relic=value)
                value = re.sub(
                    r'(•差分宇宙'
                    r'|Divergent Universe: '
                    r'|階差宇宙・'
                    r'|: Universo Diferenciado'
                    r'|Universo Diferenciado: '
                    r')', '', value)
                deep_set(new, keys=['Ornament', 'Dungeon', dungeon.name], value=value)

        # Stagnant shadows with character names
        for dungeon in DungeonDetailed.instances.values():
            if dungeon.name in dailies:
                value = dungeon.__getattribute__(ingame_lang)
                deep_set(new, keys=['Dungeon', 'Name', dungeon.name], value=value)

        # Copy dungeon i18n to double events
        def update_dungeon_names(keys):
            for dungeon in deep_get(self.argument, keys=f'{keys}.option', default=[]):
                value = deep_get(new, keys=['Dungeon', 'Name', dungeon])
                if value:
                    deep_set(new, keys=f'{keys}.{dungeon}', value=value)

        update_dungeon_names('Dungeon.NameAtDoubleCalyx')
        update_dungeon_names('Dungeon.NameAtDoubleRelic')

        # Character names
        i18n_trailblazer = {
            'cn': '开拓者',
            'cht': '開拓者',
            'jp': '開拓者',
            'en': 'Trailblazer',
            'es': 'Trailblazer',
        }
        from tasks.character.keywords import CharacterList
        from tasks.character.aired_version import get_character_version
        characters = deep_get(self.argument, keys='DungeonSupport.Character.option')
        for character in CharacterList.instances.values():
            if character.name in characters:
                value = character.__getattribute__(ingame_lang)
                version = get_character_version(character)
                if version:
                    value = f'[{version}] {value}'
                if 'trailblazer' in value.lower():
                    value = re.sub('Trailblazer', i18n_trailblazer[ingame_lang], value)
                deep_set(new, keys=['DungeonSupport', 'Character', character.name], value=value)

        # Assignments
        from tasks.assignment.keywords import AssignmentEntryDetailed
        for entry in AssignmentEntryDetailed.instances.values():
            entry: AssignmentEntryDetailed
            value = entry.__getattribute__(ingame_lang)
            for i in range(4):
                deep_set(new, keys=['Assignment', f'Name_{i + 1}', entry.name], value=value)

        # Echo of War
        dungeons = [d for d in DungeonList.instances.values() if d.is_Echo_of_War]
        for dungeon in dungeons:
            world = dungeon.plane.world
            world_name = world.__getattribute__(ingame_lang)
            dungeon_name = dungeon.__getattribute__(ingame_lang).replace('Echo of War: ', '')
            value = f'{dungeon_name} ({world_name})'
            deep_set(new, keys=['Weekly', 'Name', dungeon.name], value=value)
        # Rogue worlds
        for dungeon in [d for d in DungeonList.instances.values() if d.is_Simulated_Universe]:
            name = deep_get(new, keys=['RogueWorld', 'World', dungeon.name], default=None)
            if name:
                deep_set(new, keys=['RogueWorld', 'World', dungeon.name], value=dungeon.__getattribute__(ingame_lang))
        # Planner items
        from tasks.planner.keywords.classes import ItemBase
        for item in ItemBase.instances.values():
            item: ItemBase = item
            name = f'Item_{item.name}'
            if item.is_ItemValuable:
                continue
            if item.is_ItemCurrency or item.name == 'Tracks_of_Destiny':
                i18n = item.__getattribute__(ingame_lang)
            elif item.is_ItemExp and item.is_group_base:
                dungeon = item.dungeon
                if dungeon is None:
                    i18n = item.__getattribute__(ingame_lang)
                elif dungeon.is_Calyx_Golden_Memories:
                    i18n = i18n_memories[ingame_lang]
                elif dungeon.is_Calyx_Golden_Aether:
                    i18n = i18n_aether[ingame_lang]
                else:
                    continue
                if res := re.search(r'[:：](.*)[(（]', i18n):
                    i18n = res.group(1).strip()
            elif item.is_ItemAscension or (item.is_ItemTrace and item.is_group_base):
                dungeon = item.group_base.dungeon.name
                i18n = deep_get(new, keys=['Dungeon', 'Name', dungeon], default='Unknown_Dungeon_Come_From')
            elif item.is_ItemWeekly:
                dungeon = item.dungeon.name
                i18n = deep_get(new, keys=['Weekly', 'Name', dungeon], default='Unknown_Dungeon_Come_From')
            elif item.is_ItemCalyx and item.is_group_base:
                i18n = item.__getattribute__(ingame_lang)
            else:
                continue
            deep_set(new, keys=['Planner', name, 'name'], value=i18n)
            deep_set(new, keys=['Planner', name, 'help'], value='')

        # GUI i18n
        for path, _ in deep_iter(self.gui, depth=2):
            group, key = path
            deep_load(keys=['Gui', group], words=(key,))

        # zh-TW
        dic_repl = {
            '設置': '設定',
            '支持': '支援',
            '啓': '啟',
            '异': '異',
            '服務器': '伺服器',
            '文件': '檔案',
            '自定義': '自訂'
        }
        if lang == 'zh-TW':
            for path, value in deep_iter(new, depth=3):
                for before, after in dic_repl.items():
                    value = value.replace(before, after)
                deep_set(new, keys=path, value=value)

        write_file(filepath_i18n(lang), new)

    @cached_property
    def menu(self):
        """
        生成菜单定义文件 menu.json。
        
        该方法会根据 task.yaml 生成每个任务分组的菜单类型、页面类型和任务列表。
        Returns:
            dict: 菜单结构定义
        """
        data = {}
        for task_group in self.task.keys():
            value = deep_get(self.task, keys=[task_group, 'menu'])
            if value not in ['collapse', 'list']:
                value = 'collapse'
            deep_set(data, keys=[task_group, 'menu'], value=value)
            value = deep_get(self.task, keys=[task_group, 'page'])
            if value not in ['setting', 'tool']:
                value = 'setting'
            deep_set(data, keys=[task_group, 'page'], value=value)
            tasks = deep_get(self.task, keys=[task_group, 'tasks'], default={})
            tasks = list(tasks.keys())
            deep_set(data, keys=[task_group, 'tasks'], value=tasks)

        # Simulated universe is WIP, task won't show on GUI but can still be bound
        # e.g. `RogueUI('src', task='Rogue')`
        # Comment this for development
        # data.pop('Rogue')

        return data

    @cached_property
    def stored(self):
        """
        生成所有 stored/planner 类型参数的详细信息表。
        
        Returns:
            dict: 每个 stored 参数的详细属性（如类名、路径、i18n、顺序、颜色等）
        """
        import module.config_src.stored.classes as classes
        data = {}
        for path, value in deep_iter(self.args, depth=3):
            if value.get('type') not in ['stored', 'planner']:
                continue
            name = path[-1]
            stored = value.get('stored')
            stored_class = getattr(classes, stored)
            row = {
                'name': name,
                'path': '.'.join(path),
                'i18n': f'{path[1]}.{path[2]}.name',
                'stored': stored,
                'attrs': stored_class('')._attrs,
                'order': value.get('order', 0),
                'color': value.get('color', '#777777')
            }
            data[name] = row

        # sort by `order` ascending, but `order`==0 at last
        data = sorted(data.items(), key=lambda kv: (kv[1]['order'] == 0, kv[1]['order']))
        data = {k: v for k, v in data}
        return data

    @staticmethod
    def generate_deploy_template():
        """
        生成部署配置模板文件。
        
        该方法会根据不同平台（如通用、国内、AidLux、Docker等）生成对应的 deploy.yaml 模板，便于后续部署和环境配置。
        """
        template = poor_yaml_read(DEPLOY_TEMPLATE)
        cn = {
            'Repository': 'cn',
            'PypiMirror': 'https://pypi.tuna.tsinghua.edu.cn/simple',
            'Language': 'zh-CN',
        }
        aidlux = {
            'GitExecutable': '/usr/bin/git',
            'PythonExecutable': '/usr/bin/python',
            'RequirementsFile': './deploy/AidLux/0.92/requirements.txt',
            'AdbExecutable': '/usr/bin/adb',
        }

        docker = {
            'GitExecutable': '/usr/bin/git',
            'PythonExecutable': '/usr/local/bin/python',
            'RequirementsFile': './deploy/docker/requirements.txt',
            'AdbExecutable': '/usr/bin/adb',
        }

        def update(suffix, *args):
            file = f'./config_src/deploy.{suffix}.yaml'
            new = deepcopy(template)
            for dic in args:
                new.update(dic)
            poor_yaml_write(data=new, file=file)

        update('template')
        update('template-cn', cn)
        # update('template-AidLux', aidlux)
        # update('template-AidLux-cn', aidlux, cn)
        # update('template-docker', docker)
        # update('template-docker-cn', docker, cn)

        tpl = {
            'Repository': '{{repository}}',
            'GitExecutable': '{{gitExecutable}}',
            'PythonExecutable': '{{pythonExecutable}}',
            'AdbExecutable': '{{adbExecutable}}',
            'Language': '{{language}}',
            'Theme': '{{theme}}',
        }

        def update(file, *args):
            new = deepcopy(template)
            for dic in args:
                new.update(dic)
            poor_yaml_write(data=new, file=file)

        update('./webapp/packages/main/public/deploy.yaml.tpl', tpl)

    def check_character_templates(self):
        """
        检查角色模板图片是否存在。
        
        会遍历所有支持的角色名称，检查 assets/character 目录下是否有对应的图片文件，若缺失则输出警告。
        """
        characters = deep_get(self.args, 'Dungeon.DungeonSupport.Character.option', default=[])
        for name in characters:
            if name == 'FirstCharacter':
                continue
            if name.startswith('Trailblazer'):
                for name in [f'Stelle{name[11:]}', f'Caelum{name[11:]}']:
                    if not os.path.exists(f'./assets/character/{name}.png'):
                        print(f'WARNING: character template not exist: {name}')
            else:
                if not os.path.exists(f'./assets/character/{name}.png'):
                    print(f'WARNING: character template not exist: {name}')

    @timer
    def generate(self):
        """
        一键生成所有配置相关文件，包括 args.json、menu.json、stored.json、config_generated.py、stored_generated.py、i18n 多语言文件、部署模板等。
        
        该方法是配置生成的主入口，建议仅在主程序或开发工具中调用。
        """
        _ = self.args
        _ = self.menu
        _ = self.stored
        # _ = self.event
        # self.insert_server()
        write_file(filepath_args(), self.args)
        write_file(filepath_args('menu'), self.menu)
        write_file(filepath_args('stored'), self.stored)
        self.generate_code()
        self.generate_stored()
        for lang in LANGUAGES:
            self.generate_i18n(lang)
        self.generate_deploy_template()
        self.check_character_templates()


class ConfigUpdater:
    """
    配置更新器类，用于更新和管理现有配置。
    
    主要功能：
    1. 配置更新和转换
       - 更新现有配置到新版本
       - 处理配置项的重定向
       - 维护配置状态
    
    2. 配置验证和限制
       - 验证配置项的有效性
       - 强制某些配置项的组合限制
       - 处理配置项之间的依赖关系
    
    3. 配置读写操作
       - 读取配置文件
       - 更新配置内容
       - 写入配置文件
    
    4. 特殊功能
       - 处理配置项的回调
       - 管理隐藏的配置项
       - 处理配置模板
    
    工作流程：
    1. 读取现有配置
    2. 应用配置更新规则
    3. 处理配置重定向
    4. 更新配置状态
    5. 保存更新后的配置
    """

    # source, target, (optional)convert_func
    redirection = [
        # ('Dungeon.Dungeon.Name', 'Dungeon.Dungeon.Name', convert_20_dungeon),
        # ('Dungeon.Dungeon.NameAtDoubleCalyx', 'Dungeon.Dungeon.NameAtDoubleCalyx', convert_20_dungeon),
        # ('Dungeon.DungeonDaily.CalyxGolden', 'Dungeon.DungeonDaily.CalyxGolden', convert_20_dungeon),
        # ('Dungeon.DungeonDaily.CalyxCrimson', 'Dungeon.DungeonDaily.CalyxCrimson', convert_20_dungeon),
        # ('Rogue.RogueWorld.SimulatedUniverseElite', 'Rogue.RogueWorld.SimulatedUniverseFarm', convert_rogue_farm),
        # 2.3
        # ('Dungeon.Planner.Item_Moon_Madness_Fang', 'Dungeon.Planner.Item_Moon_Rage_Fang',
        #  convert_Item_Moon_Madness_Fang),
        # 3.1
        ('Dungeon.Dungeon.Name', 'Dungeon.Dungeon.Name', convert_31_dungeon),
        ('Dungeon.Dungeon.NameAtDoubleCalyx', 'Dungeon.Dungeon.NameAtDoubleCalyx', convert_31_dungeon),
        ('Dungeon.DungeonDaily.CalyxGolden', 'Dungeon.DungeonDaily.CalyxGolden', convert_31_dungeon),
        ('Dungeon.DungeonDaily.CalyxCrimson', 'Dungeon.DungeonDaily.CalyxCrimson', convert_31_dungeon),
        # 3.2
        ('Weekly.Weekly.Name', 'Weekly.Weekly.Name', convert_32_weekly),
    ]

    @cached_property
    def args(self):
        return read_file(filepath_args())

    def config_update(self, old, is_template=False):
        """
        Args:
            old (dict):
            is_template (bool):

        Returns:
            dict:
        """
        new = {}

        for keys, data in deep_iter(self.args, depth=3):
            value = deep_get(old, keys=keys, default=data['value'])
            typ = data['type']
            display = data.get('display')
            if is_template or value is None or value == '' \
                    or typ in ['lock', 'state'] or (display == 'hide' and typ != 'stored'):
                value = data['value']
            value = parse_value(value, data=data)
            deep_set(new, keys=keys, value=value)

        if not is_template:
            new = self.config_redirect(old, new)
        new = self.update_state(new)

        return new

    def config_redirect(self, old, new):
        """
        Convert old settings to the new.

        Args:
            old (dict):
            new (dict):

        Returns:
            dict:
        """
        for row in self.redirection:
            if len(row) == 2:
                source, target = row
                update_func = None
            elif len(row) == 3:
                source, target, update_func = row
            else:
                continue

            if isinstance(source, tuple):
                value = []
                error = False
                for attribute in source:
                    tmp = deep_get(old, keys=attribute)
                    if tmp is None:
                        error = True
                        continue
                    value.append(tmp)
                if error:
                    continue
            else:
                value = deep_get(old, keys=source)
                if value is None:
                    continue

            if update_func is not None:
                value = update_func(value)

            if isinstance(target, tuple):
                for k, v in zip(target, value):
                    # Allow update same key
                    if (deep_get(old, keys=k) is None) or (source == target):
                        deep_set(new, keys=k, value=v)
            elif (deep_get(old, keys=target) is None) or (source == target):
                deep_set(new, keys=target, value=value)

        return new

    @staticmethod
    def update_state(data):
        # Limit setting combinations
        if deep_get(data, keys='Rogue.RogueWorld.UseImmersifier') is False:
            deep_set(data, keys='Rogue.RogueWorld.UseStamina', value=False)
        if deep_get(data, keys='Rogue.RogueWorld.UseStamina') is True:
            deep_set(data, keys='Rogue.RogueWorld.UseImmersifier', value=True)
        if deep_get(data, keys='Rogue.RogueWorld.DoubleEvent') is True:
            deep_set(data, keys='Rogue.RogueWorld.UseImmersifier', value=True)
        # Store immersifier in dungeon task
        if deep_get(data, keys='Rogue.RogueWorld.UseImmersifier') is True:
            deep_set(data, keys='Dungeon.Scheduler.Enable', value=True)
        # Cloud settings
        if deep_get(data, keys='Alas.Emulator.GameClient') == 'cloud_android':
            deep_set(data, keys='Alas.Emulator.PackageName', value='CN-Official')

        return data

    def save_callback(self, key: str, value: t.Any) -> t.Iterable[t.Tuple[str, t.Any]]:
        """
        Args:
            key: Key path in config_src json, such as "Main.Emotion.Fleet1Value"
            value: Value set by user, such as "98"

        Yields:
            str: Key path to set config_src json, such as "Main.Emotion.Fleet1Record"
            any: Value to set, such as "2020-01-01 00:00:00"
        """
        if key.startswith('Dungeon.Dungeon') or key.startswith('Dungeon.DungeonDaily'):
            from tasks.dungeon.keywords.dungeon import DungeonList
            from module.exception import ScriptError
            try:
                dungeon = DungeonList.find(value)
            except ScriptError:
                return
            if key.endswith('Name'):
                if dungeon.is_Calyx_Golden:
                    yield 'Dungeon.Dungeon.NameAtDoubleCalyx', value
                elif dungeon.is_Calyx_Crimson:
                    yield 'Dungeon.Dungeon.NameAtDoubleCalyx', value
                elif dungeon.is_Cavern_of_Corrosion:
                    yield 'Dungeon.Dungeon.NameAtDoubleRelic', value
            elif key.endswith('CavernOfCorrosion'):
                yield 'Dungeon.Dungeon.NameAtDoubleRelic', value
        if key == 'Rogue.RogueWorld.UseImmersifier' and value is False:
            yield 'Rogue.RogueWorld.UseStamina', False
        if key == 'Rogue.RogueWorld.UseStamina' and value is True:
            yield 'Rogue.RogueWorld.UseImmersifier', True
        if key == 'Rogue.RogueWorld.DoubleEvent' and value is True:
            yield 'Rogue.RogueWorld.UseImmersifier', True
        if key == 'Alas.Emulator.GameClient' and value == 'cloud_android':
            yield 'Alas.Emulator.PackageName', 'CN-Official'
            yield 'Alas.Optimization.WhenTaskQueueEmpty', 'close_game'
        # Sync Dungeon.TrailblazePower and Ornament.TrailblazePower
        if key == 'Dungeon.TrailblazePower.ExtractReservedTrailblazePower':
            yield 'Ornament.TrailblazePower.ExtractReservedTrailblazePower', value
        if key == 'Dungeon.TrailblazePower.UseFuel':
            yield 'Ornament.TrailblazePower.UseFuel', value
        if key == 'Dungeon.TrailblazePower.FuelReserve':
            yield 'Ornament.TrailblazePower.FuelReserve', value
        if key == 'Ornament.TrailblazePower.ExtractReservedTrailblazePower':
            yield 'Dungeon.TrailblazePower.ExtractReservedTrailblazePower', value
        if key == 'Ornament.TrailblazePower.UseFuel':
            yield 'Dungeon.TrailblazePower.UseFuel', value
        if key == 'Ornament.TrailblazePower.FuelReserve':
            yield 'Dungeon.TrailblazePower.FuelReserve', value

    def iter_hidden_args(self, data) -> t.Iterator[str]:
        """
        Args:
            data (dict): config_src

        Yields:
            str: Arg path that should be hidden
        """
        if deep_get(data, 'Dungeon.TrailblazePower.UseFuel') == False:
            yield 'Dungeon.TrailblazePower.FuelReserve'
        if deep_get(data, 'Ornament.TrailblazePower.UseFuel') == False:
            yield 'Ornament.TrailblazePower.FuelReserve'
        if deep_get(data, 'Rogue.RogueBlessing.PresetBlessingFilter') != 'custom':
            yield 'Rogue.RogueBlessing.CustomBlessingFilter'
        if deep_get(data, 'Rogue.RogueBlessing.PresetResonanceFilter') != 'custom':
            yield 'Rogue.RogueBlessing.CustomResonanceFilter'
        if deep_get(data, 'Rogue.RogueBlessing.PresetCurioFilter') != 'custom':
            yield 'Rogue.RogueBlessing.CustomCurioFilter'
        if deep_get(data, 'Rogue.RogueWorld.WeeklyFarming', default=False) is False:
            yield 'Rogue.RogueWorld.SimulatedUniverseFarm'

    def get_hidden_args(self, data) -> t.Set[str]:
        """
        Return a set of hidden args
        """
        out = list(self.iter_hidden_args(data))
        return set(out)

    def read_file(self, config_name, is_template=False):
        """
        Read and update config_src file.

        Args:
            config_name (str): ./config_src/{file}.json
            is_template (bool):

        Returns:
            dict:
        """
        old = read_file(filepath_config(config_name))
        new = self.config_update(old, is_template=is_template)
        # The updated config_src did not write into file, although it doesn't matters.
        # Commented for performance issue
        # self.write_file(config_name, new)
        return new

    @staticmethod
    def write_file(config_name, data, mod_name='alas'):
        """
        Write config_src file.

        Args:
            config_name (str): ./config_src/{file}.json
            data (dict):
            mod_name (str):
        """
        write_file(filepath_config(config_name, mod_name), data)

    @timer
    def update_file(self, config_name, is_template=False):
        """
        Read, update and write config_src file.

        Args:
            config_name (str): ./config_src/{file}.json
            is_template (bool):

        Returns:
            dict:
        """
        data = self.read_file(config_name, is_template=is_template)
        self.write_file(config_name, data)
        return data


if __name__ == '__main__':
    """
    Process the whole config_src generation.

                 task.yaml -+----------------> menu.json
             argument.yaml -+-> args.json ---> config_generated.py
             override.yaml -+       |
                  gui.yaml --------\|
                                   ||
    (old) i18n/<lang>.json --------\\========> i18n/<lang>.json
    (old)    template.json ---------\========> template.json
    """
    # Ensure running in Alas root folder
    import os

    os.chdir(os.path.join(os.path.dirname(__file__), '../../'))

    ConfigGenerator().generate()
    ConfigUpdater().update_file('template', is_template=True)
