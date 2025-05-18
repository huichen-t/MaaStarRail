import operator
import typing as t


class SelectedGrids:
    """
    网格选择器类，用于管理和操作一组网格
    提供了丰富的网格筛选、排序和操作方法
    """
    def __init__(self, grids):
        """
        初始化网格选择器

        Args:
            grids: 网格列表
        """
        self.grids = grids
        self.indexes: t.Dict[tuple, SelectedGrids] = {}  # 用于存储索引的字典

    def __iter__(self):
        """返回网格迭代器"""
        return iter(self.grids)

    def __getitem__(self, item):
        """
        获取指定索引的网格或子网格集合

        Args:
            item: 索引或切片

        Returns:
            Grid或SelectedGrids: 单个网格或网格集合
        """
        if isinstance(item, int):
            return self.grids[item]
        else:
            return SelectedGrids(self.grids[item])

    def __contains__(self, item):
        """检查网格是否在集合中"""
        return item in self.grids

    def __str__(self):
        """返回网格集合的字符串表示"""
        return '[' + ', '.join([str(grid) for grid in self]) + ']'

    def __len__(self):
        """返回网格数量"""
        return len(self.grids)

    def __bool__(self):
        """检查是否有网格"""
        return self.count > 0

    @property
    def location(self):
        """
        获取所有网格的位置

        Returns:
            list[tuple]: 位置坐标列表
        """
        return [grid.location for grid in self.grids]

    @property
    def cost(self):
        """
        获取所有网格的消耗值

        Returns:
            list[int]: 消耗值列表
        """
        return [grid.cost for grid in self.grids]

    @property
    def weight(self):
        """
        获取所有网格的权重

        Returns:
            list[int]: 权重列表
        """
        return [grid.weight for grid in self.grids]

    @property
    def count(self):
        """
        获取网格数量

        Returns:
            int: 网格数量
        """
        return len(self.grids)

    def select(self, **kwargs):
        """
        根据属性值筛选网格

        Args:
            **kwargs: 网格的属性名和值

        Returns:
            SelectedGrids: 筛选后的网格集合
        """
        def matched(obj):
            flag = True
            for k, v in kwargs.items():
                obj_v = obj.__getattribute__(k)
                if type(obj_v) != type(v) or obj_v != v:
                    flag = False
            return flag

        return SelectedGrids([grid for grid in self.grids if matched(grid)])

    def create_index(self, *attrs):
        """
        创建网格索引

        Args:
            *attrs: 用于创建索引的属性名

        Returns:
            dict: 索引字典
        """
        indexes = {}
        for grid in self.grids:
            k = tuple(grid.__getattribute__(attr) for attr in attrs)
            try:
                indexes[k].append(grid)
            except KeyError:
                indexes[k] = [grid]

        indexes = {k: SelectedGrids(v) for k, v in indexes.items()}
        self.indexes = indexes
        return indexes

    def indexed_select(self, *values):
        """
        使用索引选择网格

        Args:
            *values: 索引值

        Returns:
            SelectedGrids: 选中的网格集合
        """
        return self.indexes.get(values, SelectedGrids([]))

    def left_join(self, right, on_attr, set_attr, default=None):
        """
        左连接操作，将右侧网格的属性值设置到左侧网格

        Args:
            right (SelectedGrids): 右侧网格集合
            on_attr: 用于匹配的属性
            set_attr: 要设置的属性
            default: 默认值

        Returns:
            SelectedGrids: 处理后的网格集合
        """
        right.create_index(*on_attr)
        for grid in self:
            attr_value = tuple([grid.__getattribute__(attr) for attr in on_attr])
            right_grid = right.indexed_select(*attr_value).first_or_none()
            if right_grid is not None:
                for attr in set_attr:
                    grid.__setattr__(attr, right_grid.__getattribute__(attr))
            else:
                for attr in set_attr:
                    grid.__setattr__(attr, default)

        return self

    def filter(self, func):
        """
        使用函数筛选网格

        Args:
            func (callable): 筛选函数，接收网格作为参数，返回布尔值

        Returns:
            SelectedGrids: 筛选后的网格集合
        """
        return SelectedGrids([grid for grid in self if func(grid)])

    def set(self, **kwargs):
        """
        设置网格属性

        Args:
            **kwargs: 属性名和值
        """
        for grid in self:
            for key, value in kwargs.items():
                grid.__setattr__(key, value)

    def get(self, attr):
        """
        获取所有网格的指定属性值

        Args:
            attr: 属性名

        Returns:
            list: 属性值列表
        """
        return [grid.__getattribute__(attr) for grid in self.grids]

    def call(self, func, **kwargs):
        """
        调用所有网格的指定方法

        Args:
            func (str): 方法名
            **kwargs: 方法参数

        Returns:
            list: 方法返回值列表
        """
        return [grid.__getattribute__(func)(**kwargs) for grid in self]

    def first_or_none(self):
        """
        获取第一个网格，如果没有则返回None

        Returns:
            Grid或None: 第一个网格或None
        """
        try:
            return self.grids[0]
        except IndexError:
            return None

    def add(self, grids):
        """
        添加网格（使用哈希去重）

        Args:
            grids(SelectedGrids): 要添加的网格集合

        Returns:
            SelectedGrids: 合并后的网格集合
        """
        return SelectedGrids(list(set(self.grids + grids.grids)))

    def add_by_eq(self, grids):
        """
        添加网格（使用相等性去重）

        Args:
            grids(SelectedGrids): 要添加的网格集合

        Returns:
            SelectedGrids: 合并后的网格集合
        """
        new = []
        for grid in self.grids + grids.grids:
            if grid not in new:
                new.append(grid)

        return SelectedGrids(new)

    def intersect(self, grids):
        """
        获取网格交集（使用哈希）

        Args:
            grids(SelectedGrids): 另一个网格集合

        Returns:
            SelectedGrids: 交集网格集合
        """
        return SelectedGrids(list(set(self.grids).intersection(set(grids.grids))))

    def intersect_by_eq(self, grids):
        """
        获取网格交集（使用相等性）

        Args:
            grids(SelectedGrids): 另一个网格集合

        Returns:
            SelectedGrids: 交集网格集合
        """
        new = []
        for grid in self.grids:
            if grid in grids.grids:
                new.append(grid)

        return SelectedGrids(new)

    def delete(self, grids):
        """
        删除指定的网格

        Args:
            grids(SelectedGrids): 要删除的网格集合

        Returns:
            SelectedGrids: 删除后的网格集合
        """
        g = [grid for grid in self.grids if grid not in grids]
        return SelectedGrids(g)

    def sort(self, *args):
        """
        根据属性排序网格

        Args:
            args (str): 用于排序的属性名

        Returns:
            SelectedGrids: 排序后的网格集合
        """
        if not self:
            return self
        if len(args):
            grids = sorted(self.grids, key=operator.attrgetter(*args))
            return SelectedGrids(grids)
        else:
            return self

    def sort_by_camera_distance(self, camera):
        """
        根据到相机的距离排序网格

        Args:
            camera (tuple): 相机位置坐标

        Returns:
            SelectedGrids: 排序后的网格集合
        """
        import numpy as np
        if not self:
            return self
        location = np.array(self.location)
        diff = np.sum(np.abs(location - camera), axis=1)
        grids = tuple(np.array(self.grids)[np.argsort(diff)])
        return SelectedGrids(grids)

    def sort_by_clock_degree(self, center=(0, 0), start=(0, 1), clockwise=True):
        """
        根据时钟角度排序网格

        Args:
            center (tuple): 中心点坐标
            start (tuple): 起始点坐标（0度位置）
            clockwise (bool): 是否顺时针排序

        Returns:
            SelectedGrids: 排序后的网格集合
        """
        import numpy as np
        if not self:
            return self
        vector = np.subtract(self.location, center)
        theta = np.arctan2(vector[:, 1], vector[:, 0]) / np.pi * 180
        vector = np.subtract(start, center)
        theta = theta - np.arctan2(vector[1], vector[0]) / np.pi * 180
        if not clockwise:
            theta = -theta
        theta[theta < 0] += 360
        grids = tuple(np.array(self.grids)[np.argsort(theta)])
        return SelectedGrids(grids)


class RoadGrids:
    """
    道路网格类，用于管理道路相关的网格集合
    提供了道路障碍物检测和路径组合等功能
    """
    def __init__(self, grids):
        """
        初始化道路网格

        Args:
            grids (list): 网格列表
        """
        self.grids = []
        for grid in grids:
            if isinstance(grid, list):
                self.grids.append(SelectedGrids(grids=grid))
            else:
                self.grids.append(SelectedGrids(grids=[grid]))

    def __str__(self):
        """返回道路网格的字符串表示"""
        return str(' - '.join([str(grid) for grid in self.grids]))

    def roadblocks(self):
        """
        获取所有道路障碍物

        Returns:
            SelectedGrids: 障碍物网格集合
        """
        grids = []
        for block in self.grids:
            if block.count == block.select(is_enemy=True).count:
                grids += block.grids
        return SelectedGrids(grids)

    def potential_roadblocks(self):
        """
        获取潜在的道路障碍物

        Returns:
            SelectedGrids: 潜在障碍物网格集合
        """
        grids = []
        for block in self.grids:
            if any([grid.is_fleet for grid in block]):
                continue
            if any([grid.is_cleared for grid in block]):
                continue
            if block.count - block.select(is_enemy=True).count == 1:
                grids += block.select(is_enemy=True).grids
        return SelectedGrids(grids)

    def first_roadblocks(self):
        """
        获取第一个道路障碍物

        Returns:
            SelectedGrids: 第一个障碍物网格集合
        """
        grids = []
        for block in self.grids:
            if any([grid.is_fleet for grid in block]):
                continue
            if any([grid.is_cleared for grid in block]):
                continue
            if block.select(is_enemy=True).count >= 1:
                grids += block.select(is_enemy=True).grids
        return SelectedGrids(grids)

    def combine(self, road):
        """
        组合两条道路

        Args:
            road (RoadGrids): 要组合的道路

        Returns:
            RoadGrids: 组合后的道路
        """
        out = RoadGrids([])
        for select_1 in self.grids:
            for select_2 in road.grids:
                select = select_1.add(select_2)
                out.grids.append(select)

        return out
