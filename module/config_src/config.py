"""
配置系统模块，提供配置的加载、保存、更新和管理功能。
包含任务调度、配置覆盖、多任务切换等核心功能。
"""

import copy
import operator
import threading
from datetime import datetime, timedelta

import pywebio

from module.base.decorator import cached_property, del_cached_property
from module.base.filter import Filter
from module.config_src.config_generated import GeneratedConfig
from module.config_src.config_manual import ManualConfig, OutputConfig
#from module.config_src.config_updater import ConfigUpdater, ensure_time, get_server_next_update, nearest_future
from module.config_src.deep import deep_get, deep_set
from module.config_src.stored.classes import iter_attribute
from module.config_src.stored.stored_generated import StoredGenerated
from module.config_src.utils import DEFAULT_TIME, dict_to_kv, filepath_config, path_to_arg
from module.config_src.watcher import ConfigWatcher
from module.exception import RequestHumanTakeover, ScriptError
from module.base.logger import logger


class TaskEnd(Exception):
    """任务结束异常，用于终止当前任务的执行"""
    pass


class Function:
    """
    任务函数类，用于表示一个可执行的任务。
    包含任务的启用状态、命令和下次运行时间。
    """
    def __init__(self, data):
        self.enable = deep_get(data, keys="Scheduler.Enable", default=False)
        self.command = deep_get(data, keys="Scheduler.Command", default="Unknown")
        self.next_run = deep_get(data, keys="Scheduler.NextRun", default=DEFAULT_TIME)

    def __str__(self):
        enable = "Enable" if self.enable else "Disable"
        return f"{self.command} ({enable}, {str(self.next_run)})"

    __repr__ = __str__

    def __eq__(self, other):
        if not isinstance(other, Function):
            return False

        if self.command == other.command and self.next_run == other.next_run:
            return True
        else:
            return False


def name_to_function(name):
    """
    将任务名称转换为Function对象。

    Args:
        name (str): 任务名称

    Returns:
        Function: 新创建的Function对象
    """
    function = Function({})
    function.command = name
    function.enable = True
    return function


class BaseConfig(ConfigUpdater, ManualConfig, GeneratedConfig, ConfigWatcher):
    """
    基础配置类，提供配置的基本功能。
    继承自多个配置相关的基类，实现配置的完整功能。
    """

    def __init__(self, config_name, task=None):
        logger.attr("Lang", self.LANG)
        # 读取 ./config_src/<config_name>.json
        self.config_name = config_name
        # YAML文件中的原始JSON数据
        self.data = {}
        # 修改过的参数。键：YAML文件中的参数路径。值：修改后的值
        self.modified = {}
        # 键：GeneratedConfig中的参数名。值：data中的路径
        self.bound = {}
        # 是否在每次变量修改后写入
        self.auto_update = True
        # 强制覆盖变量
        # 键：GeneratedConfig中的参数名。值：修改后的值
        self.overridden = {}
        # 调度器队列，在get_next_task()中更新，Function对象列表
        # pending_task: 运行时间已到，但由于任务调度尚未运行
        # waiting_task: 运行时间未到，需要等待
        self.pending_task = []
        self.waiting_task = []
        # 要运行和绑定的任务
        # task表示要在AzurLaneAutoScript类中运行的函数名
        self.task: Function
        # 模板配置用于开发工具
        self.is_template_config = config_name.startswith("template")

        if self.is_template_config:
            # 用于开发工具
            logger.info("Using template config_src, which is read only")
            self.auto_update = False
            self.task = name_to_function("template")
        self.init_task(task)


class AzurLaneConfig(ConfigUpdater, ManualConfig, GeneratedConfig, ConfigWatcher):
    """
    崩铁配置类，继承自BaseConfig，提供游戏特定的配置功能。
    """
    stop_event: threading.Event = None
    bound = {}

    # 类属性
    is_hoarding_task = True

    def __setattr__(self, key, value):
        """
        设置属性时的特殊处理。
        如果属性在bound中，则更新modified并可能触发更新。
        """
        if key in self.bound:
            path = self.bound[key]
            self.modified[path] = value
            if self.auto_update:
                self.update()
        else:
            super().__setattr__(key, value)

    def __init__(self, config_name, task=None):
        """
        初始化配置对象。

        Args:
            config_name (str): 配置文件名
            task (str, optional): 初始任务名
        """
        logger.attr("Lang", self.LANG)
        self.config_name = config_name
        self.data = {}
        self.modified = {}
        self.bound = {}
        self.auto_update = True
        self.overridden = {}
        self.pending_task = []
        self.waiting_task = []
        self.task: Function
        self.is_template_config = config_name.startswith("template")

        if self.is_template_config:
            logger.info("Using template config_src, which is read only")
            self.auto_update = False
            self.task = name_to_function("template")
        self.init_task(task)

    def init_task(self, task=None):
        """
        初始化任务。

        Args:
            task (str, optional): 任务名称
        """
        if self.is_template_config:
            return

        self.load()
        if task is None:
            # 默认绑定'Alas'，包含模拟器设置
            task = name_to_function("Alas")
        else:
            # 为调试目的绑定特定任务
            task = name_to_function(task)
        self.bind(task)
        self.task = task
        self.save()

    def load(self):
        """加载配置文件"""
        self.data = self.read_file(self.config_name)
        self.config_override()

        for path, value in self.modified.items():
            deep_set(self.data, keys=path, value=value)

    def bind(self, func, func_list=None):
        """
        绑定任务及其参数。

        Args:
            func (str, Function): 要运行的函数
            func_list (list[str]): 要绑定的任务列表
        """
        if isinstance(func, Function):
            func = func.command
        # func_list: ["Alas", <task>, *func_list]
        if func_list is None:
            func_list = []
        if func not in func_list:
            func_list.insert(0, func)
        if "Alas" not in func_list:
            func_list.insert(0, "Alas")
        logger.info(f"Bind task {func_list}")

        # 绑定参数
        visited = set()
        self.bound.clear()
        for func in func_list:
            func_data = self.data.get(func, {})
            for group, group_data in func_data.items():
                for arg, value in group_data.items():
                    path = f"{group}.{arg}"
                    if path in visited:
                        continue
                    arg = path_to_arg(path)
                    super().__setattr__(arg, value)
                    self.bound[arg] = f"{func}.{path}"
                    visited.add(path)

        # 覆盖参数
        for arg, value in self.overridden.items():
            super().__setattr__(arg, value)

    @property
    def hoarding(self):
        """
        获取任务囤积时间。

        Returns:
            timedelta: 囤积时间
        """
        minutes = int(
            deep_get(
                self.data, keys="Alas.Optimization.TaskHoardingDuration", default=0
            )
        )
        return timedelta(minutes=max(minutes, 0))

    @property
    def close_game(self):
        """
        是否在等待期间关闭游戏。

        Returns:
            bool: 是否关闭游戏
        """
        return deep_get(
            self.data, keys="Alas.Optimization.CloseGameDuringWait", default=False
        )

    @property
    def is_actual_task(self):
        """
        是否为实际任务（非Alas或template）。

        Returns:
            bool: 是否为实际任务
        """
        return self.task.command.lower() not in ['alas', 'template']

    @property
    def is_cloud_game(self):
        """
        是否为云游戏。

        Returns:
            bool: 是否为云游戏
        """
        return deep_get(
            self.data, keys="Alas.Emulator.GameClient"
        ) == 'cloud_android'

    @cached_property
    def stored(self) -> StoredGenerated:
        """
        获取存储的配置。

        Returns:
            StoredGenerated: 存储的配置对象
        """
        stored = StoredGenerated()
        # 绑定配置
        for _, value in iter_attribute(stored):
            value._bind(self)
            del_cached_property(value, '_stored')
        return stored

    def get_next_task(self):
        """
        计算任务，设置pending_task和waiting_task。
        根据任务优先级和运行时间对任务进行排序。
        """
        pending = []
        waiting = []
        error = []
        now = datetime.now()
        if AzurLaneConfig.is_hoarding_task:
            now -= self.hoarding
        for func in self.data.values():
            func = Function(func)
            if not func.enable:
                continue
            if not isinstance(func.next_run, datetime):
                error.append(func)
            elif func.next_run < now:
                pending.append(func)
            else:
                waiting.append(func)

        f = Filter(regex=r"(.*)", attr=["command"])
        f.load(self.SCHEDULER_PRIORITY)
        if pending:
            pending = f.apply(pending)
        if waiting:
            waiting = f.apply(waiting)
            waiting = sorted(waiting, key=operator.attrgetter("next_run"))
        if error:
            pending = error + pending

        self.pending_task = pending
        self.waiting_task = waiting

    def get_next(self):
        """
        获取下一个要运行的任务。

        Returns:
            Function: 要运行的命令

        Raises:
            RequestHumanTakeover: 当没有等待或待处理的任务时
        """
        self.get_next_task()

        if self.pending_task:
            AzurLaneConfig.is_hoarding_task = False
            logger.info(f"Pending tasks: {[f.command for f in self.pending_task]}")
            task = self.pending_task[0]
            logger.attr("Task", task)
            return task
        else:
            AzurLaneConfig.is_hoarding_task = True

        if self.waiting_task:
            logger.info("No task pending")
            task = copy.deepcopy(self.waiting_task[0])
            task.next_run = (task.next_run + self.hoarding).replace(microsecond=0)
            logger.attr("Task", task)
            return task
        else:
            logger.critical("No task waiting or pending")
            logger.critical("Please enable at least one task")
            raise RequestHumanTakeover

    def save(self, mod_name='alas'):
        """
        保存配置到文件。

        Args:
            mod_name (str): 模块名称

        Returns:
            bool: 是否保存成功
        """
        if not self.modified:
            return False

        for path, value in self.modified.items():
            deep_set(self.data, keys=path, value=value)

        logger.info(
            f"Save config_src {filepath_config(self.config_name, mod_name)}, {dict_to_kv(self.modified)}"
        )
        self.modified.clear()
        del_cached_property(self, 'stored')
        self.write_file(self.config_name, data=self.data)

    def update(self):
        """更新配置"""
        self.load()
        self.config_override()
        self.bind(self.task)
        self.save()

    def config_override(self):
        """
        配置覆盖。
        限制某些任务的运行时间，防止过期任务继续运行。
        """
        now = datetime.now().replace(microsecond=0)
        limited = set()

        def limit_next_run(tasks, limit):
            for task in tasks:
                if task in limited:
                    continue
                limited.add(task)
                next_run = deep_get(
                    self.data, keys=f"{task}.Scheduler.NextRun", default=None
                )
                if isinstance(next_run, datetime) and next_run > limit:
                    deep_set(self.data, keys=f"{task}.Scheduler.NextRun", value=now)

        limit_next_run(['BattlePass'], limit=now + timedelta(days=40, seconds=-1))
        limit_next_run(['Weekly'], limit=now + timedelta(days=7, seconds=-1))
        limit_next_run(self.args.keys(), limit=now + timedelta(hours=24, seconds=-1))

    def override(self, **kwargs):
        """
        覆盖任何配置。
        即使从yaml文件重新加载配置，变量也会保持覆盖状态。
        注意：此方法不可逆。

        Args:
            **kwargs: 要覆盖的配置项
        """
        for arg, value in kwargs.items():
            self.overridden[arg] = value
            super().__setattr__(arg, value)

    def set_record(self, **kwargs):
        """
        设置记录值和时间戳。

        Args:
            **kwargs: 例如，`Emotion1_Value=150`
                将设置`Emotion1_Value=150`和`Emotion1_Record=now()`
        """
        with self.multi_set():
            for arg, value in kwargs.items():
                record = arg.replace("Value", "Record")
                self.__setattr__(arg, value)
                self.__setattr__(record, datetime.now().replace(microsecond=0))

    def multi_set(self):
        """
        设置多个参数但只保存一次。

        Examples:
            with self.config_src.multi_set():
                self.config_src.foo1 = 1
                self.config_src.foo2 = 2
        """
        return MultiSetWrapper(main=self)

    def cross_get(self, keys, default=None):
        """
        从其他任务获取配置。

        Args:
            keys (str, list[str]): 如`{task}.Scheduler.Enable`
            default: 默认值

        Returns:
            Any: 配置值
        """
        return deep_get(self.data, keys=keys, default=default)

    def cross_set(self, keys, value):
        """
        设置其他任务的配置。

        Args:
            keys (str, list[str]): 如`{task}.Scheduler.Enable`
            value (Any): 要设置的值
        """
        self.modified[keys] = value
        if self.auto_update:
            self.update()

    def task_delay(self, success=None, server_update=None, target=None, minute=None, task=None):
        """
        设置Scheduler.NextRun。
        至少需要设置一个参数。
        如果设置了多个参数，使用最近的时间。

        Args:
            success (bool):
                如果为True，延迟Scheduler.SuccessInterval
                如果为False，延迟Scheduler.FailureInterval
            server_update (bool, list, str):
                如果为True，延迟到最近的Scheduler.ServerUpdate
                如果是list或str，延迟到指定的服务器更新
            target (datetime.datetime, str, list):
                延迟到指定时间
            minute (int, float, tuple):
                延迟指定分钟数
            task (str):
                跨任务设置。None表示当前任务
        """
        def ensure_delta(delay):
            return timedelta(seconds=int(ensure_time(delay, precision=3) * 60))

        run = []
        if success is not None:
            interval = (
                120
                if success
                else 30
            )
            run.append(datetime.now() + ensure_delta(interval))
        if server_update is not None:
            if server_update is True:
                server_update = self.Scheduler_ServerUpdate
            run.append(get_server_next_update(server_update))
        if target is not None:
            target = [target] if not isinstance(target, list) else target
            target = nearest_future(target)
            run.append(target)
        if minute is not None:
            run.append(datetime.now() + ensure_delta(minute))

        if len(run):
            run = min(run).replace(microsecond=0)
            kv = dict_to_kv(
                {
                    "success": success,
                    "server_update": server_update,
                    "target": target,
                    "minute": minute,
                },
                allow_none=False,
            )
            if task is None:
                task = self.task.command
            logger.info(f"Delay task `{task}` to {run} ({kv})")
            self.modified[f'{task}.Scheduler.NextRun'] = run
            self.update()
        else:
            raise ScriptError(
                "Missing argument in delay_next_run, should set at least one"
            )

    def task_call(self, task, force_call=True):
        """
        调用另一个任务运行。

        该任务将在当前任务完成后运行。
        但可能不会运行，因为：
        - 根据SCHEDULER_PRIORITY，其他任务应该先运行
        - 任务被用户禁用

        Args:
            task (str): 要调用的任务名，如`Restart`
            force_call (bool): 是否强制调用

        Returns:
            bool: 是否调用成功
        """
        if deep_get(self.data, keys=f"{task}.Scheduler.NextRun", default=None) is None:
            raise ScriptError(f"Task to call: `{task}` does not exist in user config_src")

        if force_call or self.is_task_enabled(task):
            logger.info(f"Task call: {task}")
            self.modified[f"{task}.Scheduler.NextRun"] = datetime.now().replace(
                microsecond=0
            )
            self.modified[f"{task}.Scheduler.Enable"] = True
            if self.auto_update:
                self.update()
            return True
        else:
            logger.info(f"Task call: {task} (skipped because disabled by user)")
            return False

    @staticmethod
    def task_stop(message=""):
        """
        停止当前任务。

        Args:
            message (str): 停止消息

        Raises:
            TaskEnd: 任务结束异常
        """
        if message:
            raise TaskEnd(message)
        else:
            raise TaskEnd

    def task_switched(self):
        """
        检查是否需要切换任务。

        Returns:
            bool: 是否切换了任务
        """
        # 更新事件
        if self.stop_event is not None:
            if self.stop_event.is_set():
                return True
        prev = self.task
        self.load()
        new = self.get_next()
        if prev == new:
            logger.info(f"Continue task `{new}`")
            return False
        else:
            logger.info(f"Switch task `{prev}` to `{new}`")
            return True

    def check_task_switch(self, message=""):
        """
        在任务切换时停止当前任务。

        Args:
            message (str): 停止消息

        Raises:
            TaskEnd: 任务结束异常
        """
        if self.task_switched():
            self.task_stop(message=message)

    def is_task_enabled(self, task):
        """
        检查任务是否启用。

        Args:
            task (str): 任务名称

        Returns:
            bool: 任务是否启用
        """
        return bool(self.cross_get(keys=[task, 'Scheduler', 'Enable'], default=False))

    def update_daily_quests(self):
        """
        更新每日任务。

        Raises:
            TaskEnd: 调用`DailyQuest`任务并停止当前任务
        """
        with self.multi_set():
            if self.stored.DailyActivity.is_expired():
                logger.info('DailyActivity expired')
                self.stored.DailyActivity.clear()
            if self.stored.DailyQuest.is_expired():
                logger.info('DailyQuest expired')
                q = self.stored.DailyQuest
                q.clear()
                # 假设固定任务
                q.write_quests([
                    'Complete_1_Daily_Mission',
                    'Log_in_to_the_game',
                    'Dispatch_1_assignments',
                    'Complete_Divergent_Universe_or_Simulated_Universe_1_times',
                    'Obtain_victory_in_combat_with_Support_Characters_1_times',
                    'Consume_120_Trailblaze_Power',
                ])

    def update_battle_pass_quests(self):
        """
        更新战斗通行证任务。

        Raises:
            TaskEnd: 调用`BattlePass`任务并停止当前任务
        """
        if self.stored.BattlePassWeeklyQuest.is_expired():
            if self.stored.BattlePassLevel.is_full():
                logger.info('BattlePassLevel full, no updates')
            else:
                logger.info('BattlePassTodayQuest expired')
                self.stored.BattlePassWeeklyQuest.clear()

    @property
    def DEVICE_SCREENSHOT_METHOD(self):
        """获取截图方法"""
        return self.Emulator_ScreenshotMethod

    @property
    def DEVICE_CONTROL_METHOD(self):
        """获取控制方法"""
        return self.Emulator_ControlMethod

    def temporary(self, **kwargs):
        """
        临时覆盖某些设置，稍后恢复。

        Usage:
        backup = self.config_src.cover(ENABLE_DAILY_REWARD=False)
        # do_something()
        backup.recover()

        Args:
            **kwargs: 要覆盖的设置

        Returns:
            ConfigBackup: 配置备份对象
        """
        backup = ConfigBackup(config=self)
        backup.cover(**kwargs)
        return backup


# 注册输出配置
pywebio.output.Output = OutputConfig
pywebio.pin.Output = OutputConfig


class ConfigBackup:
    """
    配置备份类，用于临时覆盖配置并恢复。
    """
    def __init__(self, config):
        """
        Args:
            config (AzurLaneConfig): 配置对象
        """
        self.config = config
        self.backup = {}
        self.kwargs = {}

    def cover(self, **kwargs):
        """
        覆盖配置。

        Args:
            **kwargs: 要覆盖的配置项
        """
        self.kwargs = kwargs
        for key, value in kwargs.items():
            self.backup[key] = self.config.__getattribute__(key)
            self.config.__setattr__(key, value)

    def recover(self):
        """恢复配置"""
        for key, value in self.backup.items():
            self.config.__setattr__(key, value)


class MultiSetWrapper:
    """
    多设置包装器，用于批量设置配置。
    """
    def __init__(self, main):
        """
        Args:
            main (AzurLaneConfig): 配置对象
        """
        self.main = main
        self.in_wrapper = False

    def __enter__(self):
        """进入上下文管理器"""
        if self.main.auto_update:
            self.main.auto_update = False
        else:
            self.in_wrapper = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        if not self.in_wrapper:
            self.main.update()
            self.main.auto_update = True
