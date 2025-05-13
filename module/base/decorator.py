"""
装饰器模块，提供各种功能装饰器。
包括配置条件装饰器、缓存属性装饰器、函数丢弃装饰器和单次运行装饰器。
"""

import random
import re
from functools import wraps
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Config:
    """
    配置条件装饰器，根据配置条件调用不同的同名函数。
    
    函数列表格式示例：
    func_list = {
        'func1': [
            {'options': {'ENABLE': True}, 'func': 1},
            {'options': {'ENABLE': False}, 'func': 1}
        ]
    }
    """
    func_list = {}

    @classmethod
    def when(cls, **kwargs):
        """
        根据配置条件装饰函数
        
        Args:
            **kwargs: AzurLaneConfig中的任何选项

        示例:
            @Config.when(USE_ONE_CLICK_RETIREMENT=True)
            def retire_ships(self, amount=None, rarity=None):
                pass

            @Config.when(USE_ONE_CLICK_RETIREMENT=False)
            def retire_ships(self, amount=None, rarity=None):
                pass
        """
        from module.logger import logger
        options = kwargs

        def decorate(func):
            name = func.__name__
            data = {'options': options, 'func': func}
            if name not in cls.func_list:
                cls.func_list[name] = [data]
            else:
                override = False
                for record in cls.func_list[name]:
                    if record['options'] == data['options']:
                        record['func'] = data['func']
                        override = True
                if not override:
                    cls.func_list[name].append(data)

            @wraps(func)
            def wrapper(self, *args, **kwargs):
                """
                根据配置条件调用相应的函数
                
                Args:
                    self: ModuleBase实例
                    *args: 位置参数
                    **kwargs: 关键字参数
                """
                for record in cls.func_list[name]:
                    # 检查所有配置条件是否匹配
                    flag = [value is None or self.config.__getattribute__(key) == value
                            for key, value in record['options'].items()]
                    if not all(flag):
                        continue

                    return record['func'](self, *args, **kwargs)

                logger.warning(f'No option fits for {name}, using the last define func.')
                return func(self, *args, **kwargs)

            return wrapper

        return decorate


class cached_property(Generic[T]):
    """
    缓存属性装饰器，添加了类型支持
    
    一个属性只计算一次，然后替换为普通属性。
    删除属性会重置该属性。
    来源: https://github.com/bottlepy/bottle/commit/fa7733e075da0d790d809aa3d2f53071897e6f76
    """

    def __init__(self, func: Callable[..., T]):
        self.func = func

    def __get__(self, obj, cls) -> T:
        if obj is None:
            return self

        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


def del_cached_property(obj, name):
    """
    安全删除缓存属性
    
    Args:
        obj: 对象实例
        name (str): 属性名
    """
    try:
        del obj.__dict__[name]
    except KeyError:
        pass


def has_cached_property(obj, name):
    """
    检查属性是否已缓存
    
    Args:
        obj: 对象实例
        name (str): 属性名
    """
    return name in obj.__dict__


def set_cached_property(obj, name, value):
    """
    设置缓存属性
    
    Args:
        obj: 对象实例
        name (str): 属性名
        value: 属性值
    """
    obj.__dict__[name] = value


def function_drop(rate=0.5, default=None):
    """
    函数丢弃装饰器，用于模拟随机模拟器卡死，用于测试目的
    
    Args:
        rate (float): 0到1之间的丢弃率
        default: 丢弃时返回的默认值

    示例:
        @function_drop(0.3)
        def click(self, button, record_check=True):
            pass

        30%的可能性:
        INFO | Dropped: module.device.device.Device.click(REWARD_GOTO_MAIN, record_check=True)
        70%的可能性:
        INFO | Click (1091,  628) @ REWARD_GOTO_MAIN
    """
    from module.logger import logger

    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if random.uniform(0, 1) > rate:
                return func(*args, **kwargs)
            else:
                cls = ''
                arguments = [str(arg) for arg in args]
                if len(arguments):
                    matched = re.search('<(.*?) object at', arguments[0])
                    if matched:
                        cls = matched.group(1) + '.'
                        arguments.pop(0)
                arguments += [f'{k}={v}' for k, v in kwargs.items()]
                arguments = ', '.join(arguments)
                logger.info(f'Dropped: {cls}{func.__name__}({arguments})')
                return default

        return wrapper

    return decorate


def run_once(f):
    """
    单次运行装饰器，确保函数只运行一次，无论被调用多少次
    
    示例:
        @run_once
        def my_function(foo, bar):
            return foo + bar

        while 1:
            my_function()

    示例:
        def my_function(foo, bar):
            return foo + bar

        action = run_once(my_function)
        while 1:
            action()
    """

    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)

    wrapper.has_run = False
    return wrapper
