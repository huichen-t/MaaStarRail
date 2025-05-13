import module.config.server as server
from module.base.decorator import cached_property, del_cached_property
from module.base.resource import Resource
from module.base.utils import *
from module.exception import ScriptError


class Button(Resource):
    """
    按钮类，用于处理游戏界面中的按钮识别和点击
    继承自Resource类，用于管理资源文件
    """
    def __init__(self, file, area, search, color, button, posi=None):
        """
        初始化按钮对象

        Args:
            file: 资源文件路径
            area: 模板裁剪区域 (x1, y1, x2, y2)
            search: 搜索区域，默认比area大20像素
            color: 资源图片的平均颜色 (R, G, B)
            button: 按钮点击区域 (x1, y1, x2, y2)
            posi: 可选，按钮位置
        """
        self.file: str = file
        self.area: t.Tuple[int, int, int, int] = area
        self.search: t.Tuple[int, int, int, int] = search
        self.color: t.Tuple[int, int, int] = color
        self._button: t.Tuple[int, int, int, int] = button
        self.posi: t.Optional[t.Tuple[int, int]] = posi

        self.resource_add(self.file)
        self._button_offset: t.Tuple[int, int] = (0, 0)

    @property
    def button(self):
        """获取考虑偏移后的按钮区域"""
        return area_offset(self._button, self._button_offset)

    def load_offset(self, button):
        """从另一个按钮加载偏移量"""
        self._button_offset = button._button_offset

    def clear_offset(self):
        """清除按钮偏移量"""
        self._button_offset = (0, 0)

    def is_offset_in(self, x=0, y=0):
        """
        检查按钮偏移是否在指定范围内

        Args:
            x: x轴偏移范围
            y: y轴偏移范围

        Returns:
            bool: 如果_button_offset在(-x, -y, x, y)范围内返回True
        """
        if x:
            if self._button_offset[0] < -x or self._button_offset[0] > x:
                return False
        if y:
            if self._button_offset[1] < -y or self._button_offset[1] > y:
                return False
        return True

    @cached_property
    def image(self):
        """加载并缓存按钮图片"""
        return load_image(self.file, self.area)

    @cached_property
    def image_luma(self):
        """获取按钮图片的亮度图"""
        return rgb2luma(self.image)

    def resource_release(self):
        """释放资源"""
        del_cached_property(self, 'image')
        del_cached_property(self, 'image_luma')
        self.clear_offset()

    def __str__(self):
        return self.file

    __repr__ = __str__

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.file)

    def __bool__(self):
        return True

    def match_color(self, image, threshold=10) -> bool:
        """
        使用平均颜色检查按钮是否出现在图像上

        Args:
            image (np.ndarray): 截图
            threshold (int): 颜色相似度阈值，默认10

        Returns:
            bool: 如果按钮出现在截图上返回True
        """
        color = get_color(image, self.area)
        return color_similar(
            color1=color,
            color2=self.color,
            threshold=threshold
        )

    def match_template(self, image, similarity=0.85, direct_match=False) -> bool:
        """
        使用模板匹配检测按钮

        对于某些按钮，其位置可能不是静态的，此时会设置_button_offset

        Args:
            image: 截图
            similarity (float): 相似度阈值，范围0-1
            direct_match: 如果为True则忽略self.search

        Returns:
            bool: 是否匹配成功
        """
        if not direct_match:
            image = crop(image, self.search, copy=False)
        res = cv2.matchTemplate(self.image, image, cv2.TM_CCOEFF_NORMED)
        _, sim, _, point = cv2.minMaxLoc(res)

        self._button_offset = np.array(point) + self.search[:2] - self.area[:2]
        return sim > similarity

    def match_template_luma(self, image, similarity=0.85, direct_match=False) -> bool:
        """
        使用亮度图进行模板匹配检测按钮

        Args:
            image: 截图
            similarity (float): 相似度阈值，范围0-1
            direct_match: 如果为True则忽略self.search

        Returns:
            bool: 是否匹配成功
        """
        if not direct_match:
            image = crop(image, self.search, copy=False)
        image = rgb2luma(image)
        res = cv2.matchTemplate(self.image_luma, image, cv2.TM_CCOEFF_NORMED)
        _, sim, _, point = cv2.minMaxLoc(res)

        self._button_offset = np.array(point) + self.search[:2] - self.area[:2]
        return sim > similarity

    def match_multi_template(self, image, similarity=0.85, direct_match=False):
        """
        使用模板匹配检测多个按钮位置

        Args:
            image: 截图
            similarity (float): 相似度阈值，范围0-1
            direct_match: 如果为True则忽略self.search

        Returns:
            list: 匹配到的所有位置列表
        """
        if not direct_match:
            image = crop(image, self.search, copy=False)
        res = cv2.matchTemplate(self.image, image, cv2.TM_CCOEFF_NORMED)
        res = cv2.inRange(res, similarity, 1.)
        try:
            points = np.array(cv2.findNonZero(res))[:, 0, :]
            points += self.search[:2]
            return points.tolist()
        except IndexError:
            # 空结果
            return []

    def match_template_color(self, image, similarity=0.85, threshold=30, direct_match=False) -> bool:
        """
        先进行模板匹配，再进行颜色匹配

        Args:
            image: 截图
            similarity (float): 相似度阈值，范围0-1
            threshold (int): 颜色相似度阈值，默认30
            direct_match: 如果为True则忽略self.search

        Returns:
            bool: 是否匹配成功
        """
        matched = self.match_template_luma(image, similarity=similarity, direct_match=direct_match)
        if not matched:
            return False

        area = area_offset(self.area, offset=self._button_offset)
        color = get_color(image, area)
        return color_similar(
            color1=color,
            color2=self.color,
            threshold=threshold
        )


class ButtonWrapper(Resource):
    """
    按钮包装器类，用于处理多语言版本的按钮
    继承自Resource类，用于管理资源文件
    """
    def __init__(self, name='MULTI_ASSETS', **kwargs):
        """
        初始化按钮包装器

        Args:
            name: 按钮名称，默认为'MULTI_ASSETS'
            **kwargs: 不同语言版本的按钮配置
        """
        self.name = name
        self.data_buttons = kwargs
        self._matched_button: t.Optional[Button] = None
        self.resource_add(f'{name}:{next(self.iter_buttons(), None)}')

    def resource_release(self):
        """释放资源"""
        del_cached_property(self, 'buttons')
        self._matched_button = None

    def __str__(self):
        return self.name

    __repr__ = __str__

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.name)

    def __bool__(self):
        return True

    def iter_buttons(self) -> t.Iterator[Button]:
        """迭代所有按钮"""
        for _, assets in self.data_buttons.items():
            if isinstance(assets, Button):
                yield assets
            elif isinstance(assets, list):
                for asset in assets:
                    yield asset

    @cached_property
    def buttons(self) -> t.List[Button]:
        """获取当前语言版本的按钮列表"""
        for trial in [server.lang, 'share', 'cn']:
            try:
                assets = self.data_buttons[trial]
                if isinstance(assets, Button):
                    return [assets]
                elif isinstance(assets, list):
                    return assets
            except KeyError:
                pass

        raise ScriptError(f'ButtonWrapper({self}) on server {server.lang} has no fallback button')

    def match_color(self, image, threshold=10) -> bool:
        """对所有按钮进行颜色匹配"""
        for assets in self.buttons:
            if assets.match_color(image, threshold=threshold):
                self._matched_button = assets
                return True
        return False

    def match_template(self, image, similarity=0.85, direct_match=False) -> bool:
        """对所有按钮进行模板匹配"""
        for assets in self.buttons:
            if assets.match_template(image, similarity=similarity, direct_match=direct_match):
                self._matched_button = assets
                return True
        return False

    def match_template_luma(self, image, similarity=0.85, direct_match=False) -> bool:
        """对所有按钮进行亮度图模板匹配"""
        for assets in self.buttons:
            if assets.match_template_luma(image, similarity=similarity, direct_match=direct_match):
                self._matched_button = assets
                return True
        return False

    def match_multi_template(self, image, similarity=0.85, threshold=5, direct_match=False):
        """
        对所有按钮进行多模板匹配

        Args:
            image: 截图
            similarity (float): 相似度阈值，范围0-1
            threshold: 分组阈值
            direct_match: 如果为True则忽略self.search

        Returns:
            list[ClickButton]: 匹配到的按钮列表
        """
        ps = []
        for assets in self.buttons:
            ps += assets.match_multi_template(image, similarity=similarity, direct_match=direct_match)
        if not ps:
            return []

        from module.core.points import Points
        ps = Points(ps).group(threshold=threshold)
        area_list = [area_offset(self.area, p - self.area[:2]) for p in ps]
        button_list = [area_offset(self.button, p - self.area[:2]) for p in ps]
        return [
            ClickButton(area=info[0], button=info[1], name=f'{self.name}_result{i}')
            for i, info in enumerate(zip(area_list, button_list))
        ]

    def match_template_color(self, image, similarity=0.85, threshold=30, direct_match=False) -> bool:
        """对所有按钮进行模板和颜色匹配"""
        for assets in self.buttons:
            if assets.match_template_color(
                    image, similarity=similarity, threshold=threshold, direct_match=direct_match):
                self._matched_button = assets
                return True
        return False

    @property
    def matched_button(self) -> Button:
        """获取匹配到的按钮"""
        if self._matched_button is None:
            return self.buttons[0]
        else:
            return self._matched_button

    @property
    def area(self) -> tuple[int, int, int, int]:
        """获取匹配按钮的区域"""
        return self.matched_button.area

    @property
    def search(self) -> tuple[int, int, int, int]:
        """获取匹配按钮的搜索区域"""
        return self.matched_button.search

    @property
    def color(self) -> tuple[int, int, int]:
        """获取匹配按钮的颜色"""
        return self.matched_button.color

    @property
    def button(self) -> tuple[int, int, int, int]:
        """获取匹配按钮的点击区域"""
        return self.matched_button.button

    @property
    def button_offset(self) -> tuple[int, int]:
        """获取匹配按钮的偏移量"""
        return self.matched_button._button_offset

    @property
    def width(self) -> int:
        """获取按钮宽度"""
        return area_size(self.area)[0]

    @property
    def height(self) -> int:
        """获取按钮高度"""
        return area_size(self.area)[1]

    def load_offset(self, button):
        """
        从另一个按钮加载偏移量

        Args:
            button (Button, ButtonWrapper): 源按钮
        """
        if isinstance(button, ButtonWrapper):
            button = button.matched_button
        for b in self.iter_buttons():
            b.load_offset(button)

    def clear_offset(self):
        """清除所有按钮的偏移量"""
        for b in self.iter_buttons():
            b.clear_offset()

    def is_offset_in(self, x=0, y=0):
        """
        检查匹配按钮的偏移是否在指定范围内

        Args:
            x: x轴偏移范围
            y: y轴偏移范围

        Returns:
            bool: 如果偏移在范围内返回True
        """
        return self.matched_button.is_offset_in(x=x, y=y)

    def load_search(self, area):
        """
        设置搜索区域
        注意：此方法不可逆

        Args:
            area: 搜索区域
        """
        for b in self.iter_buttons():
            b.search = area

    def set_search_offset(self, offset):
        """
        设置搜索区域偏移量
        兼容ALAS的offset属性
        在ALAS中：
            if self.appear(BUTTON, offset=(20, 20)):
                pass
        在SRC中：
            BUTTON.set_search_offset((20, 20))
            if self.appear(BUTTON):
                pass
        注意：search属性将被设置，且不可逆

        Args:
            offset (tuple): (x, y) 或 (left, up, right, bottom)
        """
        if len(offset) == 2:
            left, up, right, bottom = -offset[0], -offset[1], offset[0], offset[1]
        else:
            left, up, right, bottom = offset
        for b in self.iter_buttons():
            upper_left_x, upper_left_y, bottom_right_x, bottom_right_y = b.area
            b.search = (
                upper_left_x + left,
                upper_left_y + up,
                bottom_right_x + right,
                bottom_right_y + bottom,
            )


class ClickButton:
    """
    点击按钮类，用于表示一个可点击的区域
    """
    def __init__(self, area, button=None, name='CLICK_BUTTON'):
        """
        初始化点击按钮

        Args:
            area: 按钮区域
            button: 点击区域，如果为None则使用area
            name: 按钮名称
        """
        self.area = area
        if button is None:
            self.button = area
        else:
            self.button = button
        self.name = name

    def __str__(self):
        return self.name

    __repr__ = __str__

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.name)

    def __bool__(self):
        return True


