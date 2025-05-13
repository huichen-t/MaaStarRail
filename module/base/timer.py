import time
from datetime import datetime, timedelta
from functools import wraps


def timer(function):
    """
    计时器装饰器，用于统计函数运行时间
    Args:
        function: 被装饰的函数
    Returns:
        function_timer: 包装后的函数
    """
    @wraps(function)
    def function_timer(*args, **kwargs):
        t0 = time.time()  # 记录开始时间

        result = function(*args, **kwargs)  # 执行原函数
        t1 = time.time()  # 记录结束时间
        print('%s: %s s' % (function.__name__, str(round(t1 - t0, 10))))  # 打印函数名和耗时
        return result

    return function_timer


def future_time(string):
    """
    获取下一个指定时间点（未来）
    Args:
        string (str): 时间字符串，格式如 "14:59"

    Returns:
        datetime.datetime: 返回下一个指定小时和分钟的时间点（未来）
    """
    hour, minute = [int(x) for x in string.split(':')]
    future = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    future = future + timedelta(days=1) if future < datetime.now() else future
    return future


def past_time(string):
    """
    获取上一个指定时间点（过去）
    Args:
        string (str): 时间字符串，格式如 "14:59"

    Returns:
        datetime.datetime: 返回上一个指定小时和分钟的时间点（过去）
    """
    hour, minute = [int(x) for x in string.split(':')]
    past = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    past = past - timedelta(days=1) if past > datetime.now() else past
    return past


def future_time_range(string):
    """
    获取未来的时间区间
    Args:
        string (str): 时间区间字符串，格式如 "23:30-06:30"

    Returns:
        tuple(datetime.datetime): 返回(区间开始时间, 区间结束时间)
    """
    start, end = [future_time(s) for s in string.split('-')]
    if start > end:
        start = start - timedelta(days=1)
    return start, end


def time_range_active(time_range):
    """
    判断当前时间是否在指定时间区间内
    Args:
        time_range(tuple(datetime.datetime)): (区间开始时间, 区间结束时间)

    Returns:
        bool: 当前时间是否在区间内
    """
    return time_range[0] < datetime.now() < time_range[1]


class Timer:
    """
    计时器类，用于控制时间相关的操作
    主要用于处理需要等待或计时的场景，如截图、操作确认等
    """
    def __init__(self, limit, count=0):
        """
        初始化计时器
        Args:
            limit (int, float): 计时器超时时间（秒）
            count (int): 达到超时的确认次数，默认为0
                使用结构如下时，必须设置count，否则如果截图耗时大于limit会出错：
                if self.appear(MAIN_CHECK):
                    if confirm_timer.reached():
                        pass
                else:
                    confirm_timer.reset()
                建议设置count，使程序在慢电脑上更稳定
                预期速度为0.35秒/次截图
        """
        self.limit = limit  # 超时时间
        self.count = count  # 达到超时的确认次数
        self._current = 0   # 当前计时起点
        self._reach_count = count  # 当前已达超时的次数

    def start(self):
        """
        启动计时器
        Returns:
            Timer: 返回self以支持链式调用
        """
        if not self.started():
            self._current = time.time()
            self._reach_count = 0
        return self

    def started(self):
        """
        判断计时器是否已启动
        Returns:
            bool: 计时器是否已启动
        """
        return bool(self._current)

    def current(self):
        """
        获取当前已计时的秒数
        Returns:
            float: 已计时秒数
        """
        if self.started():
            return time.time() - self._current
        else:
            return 0.

    def set_current(self, current, count=0):
        """
        设置当前计时起点和已达超时次数
        Args:
            current (float): 当前计时值
            count (int): 已达超时次数
        """
        self._current = time.time() - current
        self._reach_count = count

    def reached(self):
        """
        判断是否达到超时条件
        Returns:
            bool: 是否超时且已达指定次数
        """
        self._reach_count += 1
        return time.time() - self._current > self.limit and self._reach_count > self.count

    def reset(self):
        """
        重置计时器
        Returns:
            Timer: 返回self以支持链式调用
        """
        self._current = time.time()
        self._reach_count = 0
        return self

    def clear(self):
        """
        清空计时器
        Returns:
            Timer: 返回self以支持链式调用
        """
        self._current = 0
        self._reach_count = self.count
        return self

    def reached_and_reset(self):
        """
        达到超时则重置，并返回True，否则返回False
        Returns:
            bool: 是否超时并已重置
        """
        if self.reached():
            self.reset()
            return True
        else:
            return False

    def wait(self):
        """
        阻塞等待直到超时
        """
        diff = self._current + self.limit - time.time()
        if diff > 0:
            time.sleep(diff)

    def show(self):
        """
        打印计时器信息
        """
        from module.logger import logger
        logger.info(str(self))

    def __str__(self):
        """
        计时器的字符串表示
        Returns:
            str: 格式化的计时器信息
        """
        return f'Timer(limit={round(self.current(), 3)}/{self.limit}, count={self._reach_count}/{self.count})'

    __repr__ = __str__
