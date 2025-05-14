"""
游戏界面滚动条管理模块。
提供统一的接口来处理游戏中的滚动条操作，支持垂直和水平滚动，以及自适应滚动条检测。
"""

import numpy as np
from scipy import signal

from module.base.base import ModuleBase
from module.base.button import Button, ButtonWrapper
from module.base.timer import Timer
from module.base.utils import color_similarity_2d, random_rectangle_point, rgb2gray
from module.logger import logger


class Scroll:
    """
    滚动条管理类。
    用于处理游戏中的滚动条操作，支持：
    1. 垂直和水平滚动
    2. 滚动条位置检测
    3. 滚动条拖动
    4. 页面切换
    """
    # 颜色相似度阈值，用于检测滚动条
    color_threshold = 221
    # 拖动阈值，当目标位置与当前位置的差值小于此值时认为已到达目标位置
    drag_threshold = 0.05
    # 边缘阈值，用于判断是否到达顶部或底部
    edge_threshold = 0.05
    # 边缘额外偏移量，用于处理边缘情况
    edge_add = (0.3, 0.5)

    def __init__(self, area, color, is_vertical=True, name='Scroll'):
        """
        初始化滚动条管理器。
        
        Args:
            area (Button, tuple): 滚动条的区域，可以是Button对象或坐标元组
            color (tuple): 滚动条的颜色，RGB格式
            is_vertical (bool): 是否为垂直滚动条
            name (str): 滚动条名称，用于日志输出
        """
        if isinstance(area, (Button, ButtonWrapper)):
            # name = area.name
            area = area.area
        self.area = area
        self.color = color
        self.is_vertical = is_vertical
        self.name = name

        # 计算滚动条总长度
        if self.is_vertical:
            self.total = self.area[3] - self.area[1]
        else:
            self.total = self.area[2] - self.area[0]
        # 默认值，会在match_color()中更新
        self.length = self.total / 2
        # 拖动间隔计时器
        self.drag_interval = Timer(1, count=2)
        # 拖动超时计时器
        self.drag_timeout = Timer(5, count=10)

    def match_color(self, main):
        """
        检测滚动条的位置。
        通过颜色匹配来识别滚动条在图像中的位置。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            np.ndarray: 布尔数组，表示滚动条的位置
        """
        image = main.image_crop(self.area, copy=False)
        image = color_similarity_2d(image, color=self.color)
        mask = np.max(image, axis=1 if self.is_vertical else 0) > self.color_threshold
        self.length = np.sum(mask)
        return mask

    def cal_position(self, main):
        """
        计算滚动条的当前位置。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            float: 当前位置（0到1之间）
        """
        mask = self.match_color(main)
        middle = np.mean(np.where(mask)[0])

        position = (middle - self.length / 2) / (self.total - self.length)
        position = position if position > 0 else 0.0
        position = position if position < 1 else 1.0
        logger.attr(self.name, f'{position:.2f} ({middle}-{self.length / 2})/({self.total}-{self.length})')
        return position

    def position_to_screen(self, position, random_range=(-0.05, 0.05)):
        """
        将滚动条位置转换为屏幕坐标。
        在调用此方法前需要先调用cal_position()或match_color()来获取length。
        
        Args:
            position (int, float): 目标位置（0到1之间）
            random_range (tuple): 随机范围，用于添加随机偏移
            
        Returns:
            tuple[int]: 屏幕坐标 (左上x, 左上y, 右下x, 右下y)
        """
        position = np.add(position, random_range)
        middle = position * (self.total - self.length) + self.length / 2
        middle = middle.astype(int)
        if self.is_vertical:
            middle += self.area[1]
            # 确保坐标在屏幕范围内
            while np.max(middle) >= 720:
                middle -= 2
            while np.min(middle) <= 0:
                middle += 2
            area = (self.area[0], middle[0], self.area[2], middle[1])
        else:
            middle += self.area[0]
            while np.max(middle) >= 1280:
                middle -= 2
            while np.min(middle) <= 0:
                middle += 2
            area = (middle[0], self.area[1], middle[1], self.area[3])
        return area

    def appear(self, main):
        """
        检查滚动条是否可见。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            bool: 滚动条是否可见
        """
        return np.mean(self.match_color(main)) > 0.1

    def is_draggable(self, main):
        """
        检查滚动条是否可拖动。
        如果滚动条长度接近总长度，游戏客户端可能不会响应拖动操作。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            bool: 是否可拖动
        """
        _ = self.cal_position(main)
        return self.length / self.total < 0.95

    def at_top(self, main):
        """
        检查是否在顶部。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            bool: 是否在顶部
        """
        return self.cal_position(main) < self.edge_threshold

    def at_bottom(self, main):
        """
        检查是否在底部。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            bool: 是否在底部
        """
        return self.cal_position(main) > 1 - self.edge_threshold

    def set(self, position, main, random_range=(-0.05, 0.05), distance_check=True, skip_first_screenshot=True):
        """
        设置滚动条到指定位置。
        
        Args:
            position (float, int): 目标位置（0到1之间）
            main (ModuleBase): 主模块实例
            random_range (tuple): 随机范围，用于添加随机偏移
            distance_check (bool): 是否检查拖动距离
            skip_first_screenshot (bool): 是否跳过第一次截图
            
        Returns:
            bool: 是否进行了拖动操作
        """
        logger.info(f'{self.name} set to {position}')
        self.drag_interval.clear()
        self.drag_timeout.reset()
        dragged = 0
        
        # 处理边缘情况
        if position <= self.edge_threshold:
            random_range = np.subtract(0, self.edge_add)
        if position >= 1 - self.edge_threshold:
            random_range = self.edge_add

        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                main.device.screenshot()

            current = self.cal_position(main)
            # 检查是否到达目标位置
            if abs(position - current) < self.drag_threshold:
                break
            # 处理滚动条消失的情况
            if self.length:
                self.drag_timeout.reset()
            else:
                if self.drag_timeout.reached():
                    logger.warning('Scroll disappeared, assume scroll set')
                    break
                else:
                    continue

            # 执行拖动操作
            if self.drag_interval.reached():
                p1 = random_rectangle_point(self.position_to_screen(current), n=1)
                p2 = random_rectangle_point(self.position_to_screen(position, random_range=random_range), n=1)
                main.device.swipe(p1, p2, name=self.name, distance_check=distance_check)
                self.drag_interval.reset()
                dragged += 1

        return dragged

    def set_top(self, main, random_range=(-0.05, 0.05), skip_first_screenshot=True):
        """
        滚动到顶部。
        
        Args:
            main (ModuleBase): 主模块实例
            random_range (tuple): 随机范围
            skip_first_screenshot (bool): 是否跳过第一次截图
            
        Returns:
            bool: 是否进行了拖动操作
        """
        return self.set(0.00, main=main, random_range=random_range, skip_first_screenshot=skip_first_screenshot)

    def set_bottom(self, main, random_range=(-0.05, 0.05), skip_first_screenshot=True):
        """
        滚动到底部。
        
        Args:
            main (ModuleBase): 主模块实例
            random_range (tuple): 随机范围
            skip_first_screenshot (bool): 是否跳过第一次截图
            
        Returns:
            bool: 是否进行了拖动操作
        """
        return self.set(1.00, main=main, random_range=random_range, skip_first_screenshot=skip_first_screenshot)

    def drag_page(self, page, main, random_range=(-0.05, 0.05), skip_first_screenshot=True):
        """
        向前或向后拖动一页。
        
        Args:
            page (int, float): 相对位置，1.0表示下一页，-1.0表示上一页
            main (ModuleBase): 主模块实例
            random_range (tuple): 随机范围
            skip_first_screenshot (bool): 是否跳过第一次截图
        """
        if not skip_first_screenshot:
            main.device.screenshot()
        current = self.cal_position(main)

        # 计算页面大小
        multiply = self.length / (self.total - self.length)
        target = current + page * multiply
        target = round(min(max(target, 0), 1), 3)
        return self.set(target, main=main, random_range=random_range, skip_first_screenshot=True)

    def next_page(self, main, page=0.8, random_range=(-0.01, 0.01), skip_first_screenshot=True):
        """
        滚动到下一页。
        
        Args:
            main (ModuleBase): 主模块实例
            page (float): 页面大小
            random_range (tuple): 随机范围
            skip_first_screenshot (bool): 是否跳过第一次截图
            
        Returns:
            bool: 是否进行了拖动操作
        """
        return self.drag_page(page, main=main, random_range=random_range, skip_first_screenshot=skip_first_screenshot)

    def prev_page(self, main, page=0.8, random_range=(-0.01, 0.01), skip_first_screenshot=True):
        """
        滚动到上一页。
        
        Args:
            main (ModuleBase): 主模块实例
            page (float): 页面大小
            random_range (tuple): 随机范围
            skip_first_screenshot (bool): 是否跳过第一次截图
            
        Returns:
            bool: 是否进行了拖动操作
        """
        return self.drag_page(-page, main=main, random_range=random_range, skip_first_screenshot=skip_first_screenshot)


class AdaptiveScroll(Scroll):
    """
    自适应滚动条类。
    通过图像处理自动检测滚动条位置，适用于滚动条颜色不固定的情况。
    """
    def __init__(self, area, parameters: dict = None, background=5, is_vertical=True, name='Scroll'):
        """
        初始化自适应滚动条。
        
        Args:
            area (Button, tuple): 滚动条区域
            parameters (dict): 传递给scipy.find_peaks的参数
            background (int): 背景扩展像素
            is_vertical (bool): 是否为垂直滚动条
            name (str): 滚动条名称
        """
        if parameters is None:
            parameters = {}
        self.parameters = parameters
        self.background = background
        super().__init__(area, color=(255, 255, 255), is_vertical=is_vertical, name=name)

    def match_color(self, main):
        """
        使用图像处理检测滚动条位置。
        通过查找图像中的峰值来定位滚动条。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            np.ndarray: 布尔数组，表示滚动条的位置
        """
        if self.is_vertical:
            # 垂直滚动条处理
            area = (self.area[0] - self.background, self.area[1], self.area[2] + self.background, self.area[3])
            image = main.image_crop(area, copy=False)
            image = rgb2gray(image)
            image = image.flatten()
            wlen = area[2] - area[0]
        else:
            # 水平滚动条处理
            area = (self.area[0], self.area[1] - self.background, self.area[2], self.area[3] + self.background)
            image = main.image_crop(area, copy=False)
            image = rgb2gray(image)
            image = image.flatten('F')
            wlen = area[3] - area[1]

        # 设置峰值检测参数
        parameters = {
            'height': 128,  # 最小峰值高度
            'prominence': 30,  # 最小峰值突出度
            'wlen': wlen,  # 窗口长度
            'width': 2,  # 最小峰值宽度
        }
        parameters.update(self.parameters)
        
        # 检测峰值
        peaks, _ = signal.find_peaks(image, **parameters)
        peaks //= wlen

        self.length = len(peaks)
        mask = np.zeros((self.total,), dtype=np.bool_)
        mask[peaks] = 1
        return mask
