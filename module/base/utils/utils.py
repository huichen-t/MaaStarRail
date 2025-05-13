import random



def random_normal_distribution_int(a, b, n=3):
    """
    生成区间内的正态分布随机整数
    通过多个随机数的平均值来模拟正态分布

    Args:
        a (int): 区间最小值
        b (int): 区间最大值
        n (int): 用于模拟的随机数数量，默认为3

    Returns:
        int: 符合正态分布的随机整数
    """
    a = round(a)
    b = round(b)
    if a < b:
        total = 0
        for _ in range(n):
            total += random.randint(a, b)
        return round(total / n)
    else:
        return b


def ensure_time(second, n=3, precision=3):
    """
    确保时间格式正确

    Args:
        second (int, float, tuple): 时间，如 10, (10, 30), '10, 30'
        n (int): 用于生成正态分布的随机数数量，默认为3
        precision (int): 小数位数

    Returns:
        float: 处理后的时间值
    """
    if isinstance(second, tuple):
        multiply = 10 ** precision
        result = random_normal_distribution_int(second[0] * multiply, second[1] * multiply, n) / multiply
        return round(result, precision)
    elif isinstance(second, str):
        if ',' in second:
            lower, upper = second.replace(' ', '').split(',')
            lower, upper = int(lower), int(upper)
            return ensure_time((lower, upper), n=n, precision=precision)
        if '-' in second:
            lower, upper = second.replace(' ', '').split('-')
            lower, upper = int(lower), int(upper)
            return ensure_time((lower, upper), n=n, precision=precision)
        else:
            return int(second)
    else:
        return second