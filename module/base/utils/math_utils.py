import random

import numpy as np



def limit_in(x, lower, upper):
    """
    将值限制在指定范围内

    Args:
        x: 要限制的值
        lower: 下限
        upper: 上限

    Returns:
        int, float: 限制后的值
    """
    return max(min(x, upper), lower)


def random_normal_distribution_int(a, b, n=3):
    """
    生成区间内的正态分布整数。
    通过多个随机数的平均值来模拟正态分布。

    Args:
        a (int): 区间最小值
        b (int): 区间最大值
        n (int): 模拟使用的随机数数量，默认为3

    Returns:
        int: 正态分布的随机整数
    """
    if a < b:
        output = sum([random.randint(a, b) for _ in range(n)]) / n
        return int(round(output))
    else:
        return b



def random_rectangle_point(area, n=3):
    """
    在矩形区域内随机选择一个点

    Args:
        area: 矩形区域 (左上角x, 左上角y, 右下角x, 右下角y)
        n (int): 用于生成正态分布的随机数数量，默认为3

    Returns:
        tuple(int): 随机点的坐标 (x, y)
    """
    x = random_normal_distribution_int(area[0], area[2], n=n)
    y = random_normal_distribution_int(area[1], area[3], n=n)
    return x, y


def random_rectangle_vector(vector, box, random_range=(0, 0, 0, 0), padding=15):
    """
    在矩形框内随机放置一个向量

    Args:
        vector: 向量 (x, y)
        box: 矩形框 (左上角x, 左上角y, 右下角x, 右下角y)
        random_range (tuple): 向量的随机范围 (x_min, y_min, x_max, y_max)
        padding (int): 边距

    Returns:
        tuple(int), tuple(int): 向量的起点和终点坐标
    """
    vector = np.array(vector) + random_rectangle_point(random_range)
    vector = np.round(vector).astype(int)
    half_vector = np.round(vector / 2).astype(int)
    box = np.array(box) + np.append(np.abs(half_vector) + padding, -np.abs(half_vector) - padding)
    center = random_rectangle_point(box)
    start_point = center - half_vector
    end_point = start_point + vector
    return tuple(start_point), tuple(end_point)


def random_line_segments(p1, p2, n, random_range=(0, 0, 0, 0)):
    """
    将一条线段分割成多个段

    Args:
        p1: 起点坐标 (x, y)
        p2: 终点坐标 (x, y)
        n: 分割段数
        random_range: 点的随机范围

    Returns:
        list[tuple]: 分割后的点坐标列表 [(x0, y0), (x1, y1), (x2, y2)]
    """
    return [tuple((((n - index) * p1 + index * p2) / n).astype(int) + random_rectangle_point(random_range))
            for index in range(0, n + 1)]



