import functools
import random
import time
from functools import partial

from module.logger import logger as logging_logger

"""
从 `retry` 模块复制并修改而来
"""

# 尝试导入 decorator 模块，如果不存在则定义自己的装饰器函数
try:
    from decorator import decorator
except ImportError:
    def decorator(caller):
        """
        将调用者转换为装饰器
        与 decorator 模块不同，这里不保留函数签名

        Args:
            caller: 调用者函数，格式为 caller(f, *args, **kwargs)
        """
        def decor(f):
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                return caller(f, *args, **kwargs)
            return wrapper
        return decor


def __retry_internal(f, exceptions=Exception, tries=-1, delay=0, max_delay=None, backoff=1, jitter=0,
                     logger=logging_logger):
    """
    执行函数并在失败时重试

    Args:
        f: 要执行的函数
        exceptions: 要捕获的异常或异常元组，默认为 Exception
        tries: 最大尝试次数，默认为 -1（无限次）
        delay: 重试之间的初始延迟时间（秒），默认为 0
        max_delay: 最大延迟时间（秒），默认为 None（无限制）
        backoff: 重试间隔时间的乘数，默认为 1（无退避）
        jitter: 重试间隔额外添加的随机时间（秒），默认为 0
               如果是数字则为固定值，如果是元组(min, max)则为随机范围
        logger: 失败时调用的日志记录器，默认为 retry.logging_logger
               如果为 None 则禁用日志记录

    Returns:
        函数 f 的执行结果
    """
    _tries, _delay = tries, delay
    while _tries:
        try:
            return f()
        except exceptions as e:
            _tries -= 1
            if not _tries:
                # 区别：抛出相同的异常
                raise e

            if logger is not None:
                # 区别：显示异常信息
                logger.exception(e)
                logger.warning(f'{type(e).__name__}({e}), retrying in {_delay} seconds...')

            time.sleep(_delay)
            _delay *= backoff

            # 添加随机抖动时间
            if isinstance(jitter, tuple):
                _delay += random.uniform(*jitter)
            else:
                _delay += jitter

            # 限制最大延迟时间
            if max_delay is not None:
                _delay = min(_delay, max_delay)


def retry(exceptions=Exception, tries=-1, delay=0, max_delay=None, backoff=1, jitter=0, logger=logging_logger):
    """
    返回一个重试装饰器

    Args:
        exceptions: 要捕获的异常或异常元组，默认为 Exception
        tries: 最大尝试次数，默认为 -1（无限次）
        delay: 重试之间的初始延迟时间（秒），默认为 0
        max_delay: 最大延迟时间（秒），默认为 None（无限制）
        backoff: 重试间隔时间的乘数，默认为 1（无退避）
        jitter: 重试间隔额外添加的随机时间（秒），默认为 0
               如果是数字则为固定值，如果是元组(min, max)则为随机范围
        logger: 失败时调用的日志记录器，默认为 retry.logging_logger
               如果为 None 则禁用日志记录

    Returns:
        重试装饰器
    """
    @decorator
    def retry_decorator(f, *fargs, **fkwargs):
        args = fargs if fargs else list()
        kwargs = fkwargs if fkwargs else dict()
        return __retry_internal(partial(f, *args, **kwargs), exceptions, tries, delay, max_delay, backoff, jitter,
                                logger)
    return retry_decorator


def retry_call(f, fargs=None, fkwargs=None, exceptions=Exception, tries=-1, delay=0, max_delay=None, backoff=1,
               jitter=0, logger=logging_logger):
    """
    调用函数并在失败时重新执行

    Args:
        f: 要执行的函数
        fargs: 函数的位置参数
        fkwargs: 函数的关键字参数
        exceptions: 要捕获的异常或异常元组，默认为 Exception
        tries: 最大尝试次数，默认为 -1（无限次）
        delay: 重试之间的初始延迟时间（秒），默认为 0
        max_delay: 最大延迟时间（秒），默认为 None（无限制）
        backoff: 重试间隔时间的乘数，默认为 1（无退避）
        jitter: 重试间隔额外添加的随机时间（秒），默认为 0
               如果是数字则为固定值，如果是元组(min, max)则为随机范围
        logger: 失败时调用的日志记录器，默认为 retry.logging_logger
               如果为 None 则禁用日志记录

    Returns:
        函数 f 的执行结果
    """
    args = fargs if fargs else list()
    kwargs = fkwargs if fkwargs else dict()
    return __retry_internal(partial(f, *args, **kwargs), exceptions, tries, delay, max_delay, backoff, jitter, logger)
