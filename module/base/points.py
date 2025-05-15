import numpy as np
from scipy import optimize

from module.base.utils.utils import area_pad


class Points:
    """
    点集合类，用于处理二维平面上的点集合
    支持点的基本操作、分组和连线等功能
    """
    def __init__(self, points):
        """
        初始化点集合

        Args:
            points: 点集合数据，可以是None、单个点或点数组
        """
        if points is None or len(points) == 0:
            self._bool = False
            self.points = None
        else:
            self._bool = True
            self.points = np.array(points)
            if len(self.points.shape) == 1:
                self.points = np.array([self.points])
            self.x, self.y = self.points.T

    def __str__(self):
        return str(self.points)

    __repr__ = __str__

    def __iter__(self):
        """返回点的迭代器"""
        return iter(self.points)

    def __getitem__(self, item):
        """获取指定索引的点"""
        return self.points[item]

    def __len__(self):
        """返回点的数量"""
        if self:
            return len(self.points)
        else:
            return 0

    def __bool__(self):
        """判断点集合是否为空"""
        return self._bool

    def link(self, point, is_horizontal=False):
        """
        将点集合与指定点连线，生成直线集合

        Args:
            point: 目标点坐标
            is_horizontal: 是否生成水平线

        Returns:
            Lines: 生成的直线集合
        """
        if is_horizontal:
            lines = [[y, np.pi / 2] for y in self.y]
            return Lines(lines, is_horizontal=True)
        else:
            x, y = point
            theta = -np.arctan((self.x - x) / (self.y - y))
            rho = self.x * np.cos(theta) + self.y * np.sin(theta)
            lines = np.array([rho, theta]).T
            return Lines(lines, is_horizontal=False)

    def mean(self):
        """
        计算点集合的平均点

        Returns:
            np.ndarray: 平均点坐标，如果点集合为空则返回None
        """
        if not self:
            return None

        return np.round(np.mean(self.points, axis=0)).astype(int)

    def group(self, threshold=3):
        """
        将点集合按距离分组

        Args:
            threshold: 分组距离阈值

        Returns:
            np.ndarray: 分组后的点集合
        """
        if not self:
            return np.array([])
        groups = []
        points = self.points
        if len(points) == 1:
            return np.array([points[0]])

        while len(points):
            p0, p1 = points[0], points[1:]
            distance = np.sum(np.abs(p1 - p0), axis=1)
            new = Points(np.append(p1[distance <= threshold], [p0], axis=0)).mean().tolist()
            groups.append(new)
            points = p1[distance > threshold]

        return np.array(groups)


class Lines:
    """
    直线集合类，用于处理二维平面上的直线集合
    支持直线的基本操作、分组和交点计算等功能
    """
    MID_Y = 360  # 用于计算直线中点的y坐标

    def __init__(self, lines, is_horizontal):
        """
        初始化直线集合

        Args:
            lines: 直线数据，可以是None、单条直线或直线数组
            is_horizontal: 是否为水平线集合
        """
        if lines is None or len(lines) == 0:
            self._bool = False
            self.lines = None
        else:
            self._bool = True
            self.lines = np.array(lines)
            if len(self.lines.shape) == 1:
                self.lines = np.array([self.lines])
            self.rho, self.theta = self.lines.T
        self.is_horizontal = is_horizontal

    def __str__(self):
        return str(self.lines)

    __repr__ = __str__

    def __iter__(self):
        """返回直线的迭代器"""
        return iter(self.lines)

    def __getitem__(self, item):
        """获取指定索引的直线"""
        return Lines(self.lines[item], is_horizontal=self.is_horizontal)

    def __len__(self):
        """返回直线的数量"""
        if self:
            return len(self.lines)
        else:
            return 0

    def __bool__(self):
        """判断直线集合是否为空"""
        return self._bool

    @property
    def sin(self):
        """获取所有直线的sin(theta)值"""
        return np.sin(self.theta)

    @property
    def cos(self):
        """获取所有直线的cos(theta)值"""
        return np.cos(self.theta)

    @property
    def mean(self):
        """
        计算直线集合的平均直线

        Returns:
            np.ndarray: 平均直线的参数，如果直线集合为空则返回None
        """
        if not self:
            return None
        if self.is_horizontal:
            return np.mean(self.lines, axis=0)
        else:
            x = np.mean(self.mid)
            theta = np.mean(self.theta)
            rho = x * np.cos(theta) + self.MID_Y * np.sin(theta)
            return np.array((rho, theta))

    @property
    def mid(self):
        """
        计算所有直线与y=MID_Y的交点x坐标

        Returns:
            np.ndarray: 交点x坐标数组
        """
        if not self:
            return np.array([])
        if self.is_horizontal:
            return self.rho
        else:
            return (self.rho - self.MID_Y * self.sin) / self.cos

    def get_x(self, y):
        """
        计算直线在指定y坐标处的x坐标

        Args:
            y: y坐标值

        Returns:
            np.ndarray: x坐标值
        """
        return (self.rho - y * self.sin) / self.cos

    def get_y(self, x):
        """
        计算直线在指定x坐标处的y坐标

        Args:
            x: x坐标值

        Returns:
            np.ndarray: y坐标值
        """
        return (self.rho - x * self.cos) / self.sin

    def add(self, other):
        """
        将另一个直线集合添加到当前集合

        Args:
            other: 要添加的直线集合

        Returns:
            Lines: 合并后的直线集合
        """
        if not other:
            return self
        if not self:
            return other
        lines = np.append(self.lines, other.lines, axis=0)
        return Lines(lines, is_horizontal=self.is_horizontal)

    def move(self, x, y):
        """
        移动直线集合

        Args:
            x: x方向移动距离
            y: y方向移动距离

        Returns:
            Lines: 移动后的直线集合
        """
        if not self:
            return self
        if self.is_horizontal:
            self.lines[:, 0] += y
        else:
            self.lines[:, 0] += x * self.cos + y * self.sin
        return Lines(self.lines, is_horizontal=self.is_horizontal)

    def sort(self):
        """
        按中点x坐标排序直线集合

        Returns:
            Lines: 排序后的直线集合
        """
        if not self:
            return self
        lines = self.lines[np.argsort(self.mid)]
        return Lines(lines, is_horizontal=self.is_horizontal)

    def group(self, threshold=3):
        """
        将直线集合按中点x坐标分组

        Args:
            threshold: 分组距离阈值

        Returns:
            Lines: 分组后的直线集合
        """
        if not self:
            return self
        lines = self.sort()
        prev = 0
        regrouped = []
        group = []
        for mid, line in zip(lines.mid, lines.lines):
            line = line.tolist()
            if mid - prev > threshold:
                if len(regrouped) == 0:
                    if len(group) != 0:
                        regrouped = [group]
                else:
                    regrouped += [group]
                group = [line]
            else:
                group.append(line)
            prev = mid
        regrouped += [group]
        regrouped = np.vstack([Lines(r, is_horizontal=self.is_horizontal).mean for r in regrouped])
        return Lines(regrouped, is_horizontal=self.is_horizontal)

    def distance_to_point(self, point):
        """
        计算直线到点的距离

        Args:
            point: 点坐标

        Returns:
            np.ndarray: 距离值
        """
        x, y = point
        return self.rho - x * self.cos - y * self.sin

    @staticmethod
    def cross_two_lines(lines1, lines2):
        """
        计算两条直线的交点

        Args:
            lines1: 第一条直线
            lines2: 第二条直线

        Yields:
            np.ndarray: 交点坐标
        """
        for rho1, sin1, cos1 in zip(lines1.rho, lines1.sin, lines1.cos):
            for rho2, sin2, cos2 in zip(lines2.rho, lines2.sin, lines2.cos):
                a = np.array([[cos1, sin1], [cos2, sin2]])
                b = np.array([rho1, rho2])
                yield np.linalg.solve(a, b)

    def cross(self, other):
        """
        计算与另一个直线集合的交点

        Args:
            other: 另一个直线集合

        Returns:
            Points: 交点集合
        """
        points = np.vstack(self.cross_two_lines(self, other))
        points = Points(points)
        return points

    def delete(self, other, threshold=3):
        """
        删除与另一个直线集合相近的直线

        Args:
            other: 另一个直线集合
            threshold: 删除阈值

        Returns:
            Lines: 删除后的直线集合
        """
        if not self:
            return self

        other_mid = other.mid
        lines = []
        for mid, line in zip(self.mid, self.lines):
            if np.any(np.abs(other_mid - mid) < threshold):
                continue
            lines.append(line)

        return Lines(lines, is_horizontal=self.is_horizontal)


def area2corner(area):
    """
    将矩形区域转换为四个角点坐标

    Args:
        area: (x1, y1, x2, y2) 矩形区域坐标

    Returns:
        np.ndarray: [左上角, 右上角, 左下角, 右下角] 坐标数组
    """
    return np.array([[area[0], area[1]], [area[2], area[1]], [area[0], area[3]], [area[2], area[3]]])


def corner2area(corner):
    """
    将四个角点坐标转换为矩形区域

    Args:
        corner: [左上角, 右上角, 左下角, 右下角] 坐标数组

    Returns:
        np.ndarray: (x1, y1, x2, y2) 矩形区域坐标
    """
    x, y = np.array(corner).T
    return np.rint([np.min(x), np.min(y), np.max(x), np.max(y)]).astype(int)


def corner2inner(corner):
    """
    计算梯形内接最大矩形

    Args:
        corner: ((x0, y0), (x1, y1), (x2, y2), (x3, y3)) 梯形四个角点坐标

    Returns:
        tuple[int]: (左上角x, 左上角y, 右下角x, 右下角y) 矩形区域坐标
    """
    x0, y0, x1, y1, x2, y2, x3, y3 = np.array(corner).flatten()
    area = tuple(np.rint((max(x0, x2), max(y0, y1), min(x1, x3), min(y2, y3))).astype(int))
    return area


def corner2outer(corner):
    """
    计算梯形外接最小矩形

    Args:
        corner: ((x0, y0), (x1, y1), (x2, y2), (x3, y3)) 梯形四个角点坐标

    Returns:
        tuple[int]: (左上角x, 左上角y, 右下角x, 右下角y) 矩形区域坐标
    """
    x0, y0, x1, y1, x2, y2, x3, y3 = np.array(corner).flatten()
    area = tuple(np.rint((min(x0, x2), min(y0, y1), max(x1, x3), max(y2, y3))).astype(int))
    return area


def trapezoid2area(corner, pad=0):
    """
    将梯形角点转换为矩形区域

    Args:
        corner: ((x0, y0), (x1, y1), (x2, y2), (x3, y3)) 梯形四个角点坐标
        pad (int): 
            正值表示内接矩形
            负值或0表示外接矩形

    Returns:
        tuple[int]: (左上角x, 左上角y, 右下角x, 右下角y) 矩形区域坐标
    """
    if pad > 0:
        return area_pad(corner2inner(corner), pad=pad)
    elif pad < 0:
        return area_pad(corner2outer(corner), pad=pad)
    else:
        return area_pad(corner2area(corner), pad=pad)


def points_to_area_generator(points, shape):
    """
    将点集合转换为区域生成器

    Args:
        points (np.ndarray): N x 2 的点坐标数组
        shape (tuple): (x, y) 形状

    Yields:
        tuple, np.ndarray: (x, y) 索引, [左上角, 右上角, 左下角, 右下角] 区域坐标
    """
    points = points.reshape(*shape[::-1], 2)
    for y in range(shape[1] - 1):
        for x in range(shape[0] - 1):
            area = np.array([points[y, x], points[y, x + 1], points[y + 1, x], points[y + 1, x + 1]])
            yield ((x, y), area)


def get_map_inner(points):
    """
    计算点集合的中心点

    Args:
        points (np.ndarray): N x 2 的点坐标数组

    Yields:
        np.ndarray: (x, y) 中心点坐标
    """
    points = np.array(points)
    if len(points.shape) == 1:
        points = np.array([points])

    return np.mean(points, axis=0)


def separate_edges(edges, inner):
    """
    根据内部点将边集合分为上下两部分

    Args:
        edges: 边集合，包含浮点数或整数
        inner (float, int): 用于分隔的内部点

    Returns:
        float, float: 下边界和上边界，如果未找到则返回None
    """
    if len(edges) == 0:
        return None, None
    elif len(edges) == 1:
        edge = edges[0]
        return (None, edge) if edge > inner else (edge, None)
    else:
        lower = [edge for edge in edges if edge < inner]
        upper = [edge for edge in edges if edge > inner]
        lower = lower[0] if len(lower) else None
        upper = upper[-1] if len(upper) else None
        return lower, upper


def perspective_transform(points, data):
    """
    对点集合进行透视变换

    Args:
        points: 形状为(n, 2)的2D数组
        data: 透视变换数据，形状为(3, 3)的2D数组
            详见 https://web.archive.org/web/20150222120106/xenia.media.mit.edu/~cwren/interpolator/

    Returns:
        np.ndarray: 形状为(n, 2)的变换后点坐标数组
    """
    points = np.pad(np.array(points), ((0, 0), (0, 1)), mode='constant', constant_values=1)
    matrix = data.dot(points.T)
    x, y = matrix[0] / matrix[2], matrix[1] / matrix[2]
    points = np.array([x, y]).T
    return points


def fit_points(points, mod, encourage=1):
    """
    在具有共同差值的点集合中找到最接近的点

    Args:
        points: 图像上的点集合，形状为(n, 2)的2D数组
        mod: 点的共同差值，格式为(x, y)
        encourage (int, float): 描述如何拟合点集合，单位为像素
            较小的值更接近局部最小值，较大的值更接近全局最小值

    Returns:
        np.ndarray: (x, y) 最接近的点坐标
    """
    encourage = np.square(encourage)
    mod = np.array(mod)
    points = np.array(points) % mod
    points = np.append(points - mod, points, axis=0)

    def cal_distance(point):
        distance = np.linalg.norm(points - point, axis=1)
        return np.sum(1 / (1 + np.exp(encourage / distance) / distance))

    # 使用暴力搜索全局最小值
    area = np.append(-mod - 10, mod + 10)
    result = optimize.brute(cal_distance, ((area[0], area[2]), (area[1], area[3])))
    return result % mod
