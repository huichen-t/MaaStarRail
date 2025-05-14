import random
import re
import cv2
import numpy as np
from PIL import Image

from module.base.utils.math_utils import limit_in

REGEX_NODE = re.compile(r'(-?[A-Za-z]+)(-?\d+)')

def match_template(image, template, similarity=0.85):
    """
    模板匹配函数

    Args:
        image (np.ndarray): 截图
        template (np.ndarray): 模板图片
        similarity (float): 相似度阈值，范围0-1

    Returns:
        bool: 是否匹配成功
    """
    res = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    _, sim, _, point = cv2.minMaxLoc(res)
    return sim > similarity






def area_offset(area, offset):
    """
    移动区域

    Args:
        area: 区域 (左上角x, 左上角y, 右下角x, 右下角y)
        offset: 偏移量 (x, y)

    Returns:
        tuple: 移动后的区域
    """
    upper_left_x, upper_left_y, bottom_right_x, bottom_right_y = area
    x, y = offset
    return upper_left_x + x, upper_left_y + y, bottom_right_x + x, bottom_right_y + y


def area_pad(area, pad=10):
    """
    区域内部偏移

    Args:
        area: 区域 (左上角x, 左上角y, 右下角x, 右下角y)
        pad (int): 偏移量

    Returns:
        tuple: 偏移后的区域
    """
    upper_left_x, upper_left_y, bottom_right_x, bottom_right_y = area
    return upper_left_x + pad, upper_left_y + pad, bottom_right_x - pad, bottom_right_y - pad



def area_limit(area1, area2):
    """
    将一个区域限制在另一个区域内

    Args:
        area1: 要限制的区域 (左上角x, 左上角y, 右下角x, 右下角y)
        area2: 限制区域 (左上角x, 左上角y, 右下角x, 右下角y)

    Returns:
        tuple: 限制后的区域
    """
    x_lower, y_lower, x_upper, y_upper = area2
    return (
        limit_in(area1[0], x_lower, x_upper),
        limit_in(area1[1], y_lower, y_upper),
        limit_in(area1[2], x_lower, x_upper),
        limit_in(area1[3], y_lower, y_upper),
    )


def area_size(area):
    """
    获取区域的尺寸

    Args:
        area: 区域 (左上角x, 左上角y, 右下角x, 右下角y)

    Returns:
        tuple: 区域的宽度和高度 (width, height)
    """
    return (
        max(area[2] - area[0], 0),
        max(area[3] - area[1], 0)
    )


def area_center(area):
    """
    获取区域的中心点

    Args:
        area: 区域 (左上角x, 左上角y, 右下角x, 右下角y)

    Returns:
        tuple: 中心点坐标 (x, y)
    """
    x1, y1, x2, y2 = area
    return (x1 + x2) / 2, (y1 + y2) / 2


def point_limit(point, area):
    """
    将点限制在区域内

    Args:
        point: 点坐标 (x, y)
        area: 区域 (左上角x, 左上角y, 右下角x, 右下角y)

    Returns:
        tuple: 限制后的点坐标
    """
    return (
        limit_in(point[0], area[0], area[2]),
        limit_in(point[1], area[1], area[3])
    )


def point_in_area(point, area, threshold=5):
    """
    检查点是否在区域内

    Args:
        point: 点坐标 (x, y)
        area: 区域 (左上角x, 左上角y, 右下角x, 右下角y)
        threshold: 阈值

    Returns:
        bool: 点是否在区域内
    """
    return area[0] - threshold < point[0] < area[2] + threshold and area[1] - threshold < point[1] < area[3] + threshold


def area_in_area(area1, area2, threshold=5):
    """
    检查一个区域是否在另一个区域内

    Args:
        area1: 要检查的区域 (左上角x, 左上角y, 右下角x, 右下角y)
        area2: 目标区域 (左上角x, 左上角y, 右下角x, 右下角y)
        threshold: 阈值

    Returns:
        bool: 区域1是否在区域2内
    """
    return area2[0] - threshold <= area1[0] \
        and area2[1] - threshold <= area1[1] \
        and area1[2] <= area2[2] + threshold \
        and area1[3] <= area2[3] + threshold


def area_cross_area(area1, area2, threshold=5):
    """
    检查两个区域是否相交

    Args:
        area1: 区域1 (左上角x, 左上角y, 右下角x, 右下角y)
        area2: 区域2 (左上角x, 左上角y, 右下角x, 右下角y)
        threshold: 阈值

    Returns:
        bool: 区域是否相交
    """
    xa1, ya1, xa2, ya2 = area1
    xb1, yb1, xb2, yb2 = area2
    return abs(xb2 + xb1 - xa2 - xa1) <= xa2 - xa1 + xb2 - xb1 + threshold * 2 \
        and abs(yb2 + yb1 - ya2 - ya1) <= ya2 - ya1 + yb2 - yb1 + threshold * 2


def col2name(col):
    """
    将列索引转换为Excel风格的列名

    Args:
        col: 列索引（从0开始）

    Returns:
        str: Excel风格的列名

    示例:
        0 -> A, 3 -> D, 35 -> AJ, -1 -> -A
    """
    col_neg = col < 0
    if col_neg:
        col_num = -col
    else:
        col_num = col + 1  # 转换为1-based索引
    col_str = ''

    while col_num:
        remainder = col_num % 26
        if remainder == 0:
            remainder = 26
        col_letter = chr(remainder + 64)
        col_str = col_letter + col_str
        col_num = int((col_num - 1) / 26)

    if col_neg:
        return '-' + col_str
    else:
        return col_str


def name2col(col_str):
    """
    将Excel风格的列名转换为列索引

    Args:
        col_str: Excel风格的列名

    Returns:
        int: 列索引（从0开始）
    """
    expn = 0
    col = 0
    col_neg = col_str.startswith('-')
    col_str = col_str.strip('-').upper()

    for char in reversed(col_str):
        col += (ord(char) - 64) * (26 ** expn)
        expn += 1

    if col_neg:
        return -col
    else:
        return col - 1  # 转换为0-based索引


def node2location(node):
    """
    将节点名称转换为坐标

    Args:
        node (str): 节点名称，如 'E3'

    Returns:
        tuple[int]: 坐标 (x, y)
    """
    res = REGEX_NODE.search(node)
    if res:
        x, y = res.group(1), res.group(2)
        y = int(y)
        if y > 0:
            y -= 1
        return name2col(x), y
    else:
        return ord(node[0]) % 32 - 1, int(node[1:]) - 1


def location2node(location):
    """
    将坐标转换为Excel风格的单元格名称
    支持负值

    Args:
        location (tuple[int]): 坐标 (x, y)

    Returns:
        str: Excel风格的单元格名称
    """
    x, y = location
    if y >= 0:
        y += 1
    return col2name(x) + str(y)


def xywh2xyxy(area):
    """
    将 (x, y, width, height) 格式转换为 (x1, y1, x2, y2) 格式
    """
    x, y, w, h = area
    return x, y, x + w, y + h


def xyxy2xywh(area):
    """
    将 (x1, y1, x2, y2) 格式转换为 (x, y, width, height) 格式
    """
    x1, y1, x2, y2 = area
    return min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)


def load_image(file, area=None):
    """
    加载图像，类似PIL.Image.open，但会移除alpha通道

    Args:
        file (str): 图像文件路径
        area (tuple): 裁剪区域

    Returns:
        np.ndarray: 图像数组
    """
    image = Image.open(file)
    if area is not None:
        image = image.crop(area)
    image = np.array(image)
    channel = image.shape[2] if len(image.shape) > 2 else 1
    if channel > 3:
        image = image[:, :, :3].copy()
    return image


def save_image(image, file):
    """
    保存图像，类似PIL.Image.save

    Args:
        image (np.ndarray): 图像数组
        file (str): 保存路径
    """
    Image.fromarray(image).save(file)


def copy_image(src):
    """
    复制图像，比image.copy()稍快

    复制1280*720*3图像的时间消耗：
        image.copy()      0.743ms
        copy_image(image) 0.639ms
    """
    dst = np.empty_like(src)
    cv2.copyTo(src, None, dst)
    return dst


def crop(image, area, copy=True):
    """
    裁剪图像，类似PIL.Image.crop，但使用OpenCV/NumPy实现
    如果裁剪区域超出图像范围，会提供黑色背景

    Args:
        image (np.ndarray): 图像数组
        area: 裁剪区域
        copy (bool): 是否复制图像

    Returns:
        np.ndarray: 裁剪后的图像
    """
    x1, y1, x2, y2 = area
    x1 = round(x1)
    y1 = round(y1)
    x2 = round(x2)
    y2 = round(y2)
    shape = image.shape
    h = shape[0]
    w = shape[1]
    overflow = False
    if y1 >= 0:
        top = 0
        if y1 >= h:
            overflow = True
    else:
        top = -y1
    if y2 > h:
        bottom = y2 - h
    else:
        bottom = 0
        if y2 <= 0:
            overflow = True
    if x1 >= 0:
        left = 0
        if x1 >= w:
            overflow = True
    else:
        left = -x1
    if x2 > w:
        right = x2 - w
    else:
        right = 0
        if x2 <= 0:
            overflow = True
    if overflow:
        if len(shape) == 2:
            size = (y2 - y1, x2 - x1)
        else:
            size = (y2 - y1, x2 - x1, shape[2])
        return np.zeros(size, dtype=image.dtype)
    if x1 < 0:
        x1 = 0
    if y1 < 0:
        y1 = 0
    if x2 < 0:
        x2 = 0
    if y2 < 0:
        y2 = 0
    image = image[y1:y2, x1:x2]
    if top or bottom or left or right:
        if len(shape) == 2:
            value = 0
        else:
            value = tuple(0 for _ in range(image.shape[2]))
        return cv2.copyMakeBorder(image, top, bottom, left, right, borderType=cv2.BORDER_CONSTANT, value=value)
    elif copy:
        return copy_image(image)
    else:
        return image


def resize(image, size):
    """
    调整图像大小，类似PIL.Image.resize，但使用OpenCV实现
    PIL默认使用PIL.Image.NEAREST插值方法

    Args:
        image (np.ndarray): 图像数组
        size: 目标大小 (x, y)

    Returns:
        np.ndarray: 调整大小后的图像
    """
    return cv2.resize(image, size, interpolation=cv2.INTER_NEAREST)


def image_channel(image):
    """
    获取图像的通道数

    Args:
        image (np.ndarray): 图像数组

    Returns:
        int: 通道数（0表示灰度图，3表示RGB）
    """
    return image.shape[2] if len(image.shape) == 3 else 0


def image_size(image):
    """
    获取图像的尺寸

    Args:
        image (np.ndarray): 图像数组

    Returns:
        tuple: 图像的宽度和高度 (width, height)
    """
    shape = image.shape
    return shape[1], shape[0]


def image_paste(image, background, origin):
    """
    将图像粘贴到背景上
    此方法不返回值，而是直接更新background数组

    Args:
        image: 要粘贴的图像
        background: 背景图像
        origin: 粘贴位置 (x, y)
    """
    x, y = origin
    w, h = image_size(image)
    background[y:y + h, x:x + w] = image


def rgb2gray(image):
    """
    将RGB图像转换为灰度图
    gray = ( MAX(r, g, b) + MIN(r, g, b)) / 2

    Args:
        image (np.ndarray): RGB图像数组

    Returns:
        np.ndarray: 灰度图像数组
    """
    r, g, b = cv2.split(image)
    maximum = cv2.max(r, g)
    cv2.min(r, g, dst=r)
    cv2.max(maximum, b, dst=maximum)
    cv2.min(r, b, dst=r)
    cv2.convertScaleAbs(maximum, alpha=0.5, dst=maximum)
    cv2.convertScaleAbs(r, alpha=0.5, dst=r)
    cv2.add(maximum, r, dst=maximum)
    return maximum


def rgb2hsv(image):
    """
    将RGB颜色空间转换为HSV颜色空间
    HSV表示色相(Hue)、饱和度(Saturation)、明度(Value)

    Args:
        image (np.ndarray): RGB图像数组

    Returns:
        np.ndarray: HSV图像数组，色相(0~360)、饱和度(0~100)、明度(0~100)
    """
    image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(float)
    cv2.multiply(image, (360 / 180, 100 / 255, 100 / 255, 0), dst=image)
    return image


def rgb2yuv(image):
    """
    将RGB转换为YUV颜色空间

    Args:
        image (np.ndarray): RGB图像数组

    Returns:
        np.ndarray: YUV图像数组
    """
    image = cv2.cvtColor(image, cv2.COLOR_RGB2YUV)
    return image


def rgb2luma(image):
    """
    将RGB转换为YUV颜色空间的Y通道（亮度）

    Args:
        image (np.ndarray): RGB图像数组

    Returns:
        np.ndarray: 亮度图像数组
    """
    image = cv2.cvtColor(image, cv2.COLOR_RGB2YUV)
    luma, _, _ = cv2.split(image)
    return luma


def get_color(image, area):
    """
    计算图像特定区域的平均颜色

    Args:
        image (np.ndarray): 图像数组
        area (tuple): 区域 (左上角x, 左上角y, 右下角x, 右下角y)

    Returns:
        tuple: RGB颜色值 (r, g, b)
    """
    temp = crop(image, area, copy=False)
    color = cv2.mean(temp)
    return color[:3]


def get_bbox(image, threshold=0):
    """
    获取图像中非黑色区域的边界框
    类似PIL.Image.getbbox()的NumPy实现

    Args:
        image (np.ndarray): 图像数组
        threshold (int): 颜色阈值，小于等于此值的像素被视为黑色

    Returns:
        tuple: 边界框 (左上角x, 左上角y, 右下角x, 右下角y)
    """
    if image_channel(image) == 3:
        image = np.max(image, axis=2)
    x = np.where(np.max(image, axis=0) > threshold)[0]
    y = np.where(np.max(image, axis=1) > threshold)[0]
    return x[0], y[0], x[-1] + 1, y[-1] + 1


def get_bbox_reversed(image, threshold=255):
    """
    获取图像中非白色区域的边界框
    与get_bbox类似，但用于黑色内容在白色背景上的情况

    Args:
        image (np.ndarray): 图像数组
        threshold (int): 颜色阈值，大于等于此值的像素被视为白色

    Returns:
        tuple: 边界框 (左上角x, 左上角y, 右下角x, 右下角y)
    """
    if image_channel(image) == 3:
        image = np.min(image, axis=2)
    x = np.where(np.min(image, axis=0) < threshold)[0]
    y = np.where(np.min(image, axis=1) < threshold)[0]
    return x[0], y[0], x[-1] + 1, y[-1] + 1


def color_similarity(color1, color2):
    """
    计算两个颜色的相似度

    Args:
        color1 (tuple): RGB颜色值 (r, g, b)
        color2 (tuple): RGB颜色值 (r, g, b)

    Returns:
        int: 颜色相似度值
    """
    diff_r = color1[0] - color2[0]
    diff_g = color1[1] - color2[1]
    diff_b = color1[2] - color2[2]

    max_positive = 0
    max_negative = 0
    if diff_r > max_positive:
        max_positive = diff_r
    elif diff_r < max_negative:
        max_negative = diff_r
    if diff_g > max_positive:
        max_positive = diff_g
    elif diff_g < max_negative:
        max_negative = diff_g
    if diff_b > max_positive:
        max_positive = diff_b
    elif diff_b < max_negative:
        max_negative = diff_b

    diff = max_positive - max_negative
    return diff


def color_similar(color1, color2, threshold=10):
    """
    判断两个颜色是否相似
    如果容差小于等于阈值，则认为颜色相似
    容差 = Max(正差值_rgb) + Max(-负差值_rgb)
    与Photoshop中的容差计算方式相同

    Args:
        color1 (tuple): RGB颜色值 (r, g, b)
        color2 (tuple): RGB颜色值 (r, g, b)
        threshold (int): 阈值，默认为10

    Returns:
        bool: 颜色是否相似
    """
    diff_r = color1[0] - color2[0]
    diff_g = color1[1] - color2[1]
    diff_b = color1[2] - color2[2]

    max_positive = 0
    max_negative = 0
    if diff_r > max_positive:
        max_positive = diff_r
    elif diff_r < max_negative:
        max_negative = diff_r
    if diff_g > max_positive:
        max_positive = diff_g
    elif diff_g < max_negative:
        max_negative = diff_g
    if diff_b > max_positive:
        max_positive = diff_b
    elif diff_b < max_negative:
        max_negative = diff_b

    diff = max_positive - max_negative
    return diff <= threshold


def color_similar_1d(image, color, threshold=10):
    """
    计算一维图像数组与颜色的相似度

    Args:
        image (np.ndarray): 一维图像数组
        color: RGB颜色值 (r, g, b)
        threshold (int): 阈值，默认为10

    Returns:
        np.ndarray: 布尔数组，表示每个像素是否与目标颜色相似
    """
    diff = image.astype(int) - color
    diff = np.max(np.maximum(diff, 0), axis=1) - np.min(np.minimum(diff, 0), axis=1)
    return diff <= threshold


def color_similarity_2d(image, color):
    """
    计算二维图像数组与颜色的相似度

    Args:
        image: 二维图像数组
        color: RGB颜色值 (r, g, b)

    Returns:
        np.ndarray: 相似度数组，值范围0-255
    """
    diff = cv2.subtract(image, (*color, 0))
    r, g, b = cv2.split(diff)
    cv2.max(r, g, dst=r)
    cv2.max(r, b, dst=r)
    positive = r
    cv2.subtract((*color, 0), image, dst=diff)
    r, g, b = cv2.split(diff)
    cv2.max(r, g, dst=r)
    cv2.max(r, b, dst=r)
    negative = r
    cv2.add(positive, negative, dst=positive)
    cv2.subtract(255, positive, dst=positive)
    return positive


def extract_letters(image, letter=(255, 255, 255), threshold=128):
    """
    提取图像中的文字
    将文字颜色设为黑色，背景颜色设为白色

    Args:
        image: 图像数组
        letter (tuple): 文字RGB颜色
        threshold (int): 阈值

    Returns:
        np.ndarray: 处理后的图像数组
    """
    diff = cv2.subtract(image, (*letter, 0))
    r, g, b = cv2.split(diff)
    cv2.max(r, g, dst=r)
    cv2.max(r, b, dst=r)
    positive = r
    cv2.subtract((*letter, 0), image, dst=diff)
    r, g, b = cv2.split(diff)
    cv2.max(r, g, dst=r)
    cv2.max(r, b, dst=r)
    negative = r
    cv2.add(positive, negative, dst=positive)
    if threshold != 255:
        cv2.convertScaleAbs(positive, alpha=255.0 / threshold, dst=positive)
    return positive


def extract_white_letters(image, threshold=128):
    """
    提取图像中的白色文字
    将文字颜色设为黑色，背景颜色设为白色
    此函数会抑制彩色像素（非灰度像素）

    Args:
        image: 图像数组
        threshold (int): 阈值

    Returns:
        np.ndarray: 处理后的图像数组
    """
    r, g, b = cv2.split(cv2.subtract((255, 255, 255, 0), image))
    maximum = cv2.max(r, g)
    cv2.min(r, g, dst=r)
    cv2.max(maximum, b, dst=maximum)
    cv2.min(r, b, dst=r)

    cv2.convertScaleAbs(maximum, alpha=0.5, dst=maximum)
    cv2.convertScaleAbs(r, alpha=0.5, dst=r)
    cv2.subtract(maximum, r, dst=r)
    cv2.add(maximum, r, dst=maximum)
    if threshold != 255:
        cv2.convertScaleAbs(maximum, alpha=255.0 / threshold, dst=maximum)
    return maximum


def color_mapping(image, max_multiply=2):
    """
    将颜色映射到0-255范围
    最小颜色映射到0，最大颜色映射到255，颜色最多放大2倍

    Args:
        image (np.ndarray): 图像数组
        max_multiply (int, float): 最大放大倍数

    Returns:
        np.ndarray: 映射后的图像数组
    """
    image = image.astype(float)
    low, high = np.min(image), np.max(image)
    multiply = min(255 / (high - low), max_multiply)
    add = (255 - multiply * (low + high)) / 2
    cv2.multiply(image, multiply, dst=image)
    cv2.add(image, add, dst=image)
    image[image > 255] = 255
    image[image < 0] = 0
    return image.astype(np.uint8)


def image_left_strip(image, threshold, length):
    """
    从图像左侧去除指定长度的内容
    例如在 'DAILY:200/200' 中去除 'DAILY:' 得到 '200/200'

    Args:
        image (np.ndarray): 图像数组
        threshold (int): 阈值（0-255）
            亮度低于此值的第一个列将被视为左边界
        length (int): 从左边界开始要去除的长度

    Returns:
        np.ndarray: 处理后的图像
    """
    brightness = np.mean(image, axis=0)
    match = np.where(brightness < threshold)[0]

    if len(match):
        left = match[0] + length
        total = image.shape[1]
        if left < total:
            image = image[:, left:]
    return image


def red_overlay_transparency(color1, color2, red=247):
    """
    计算红色叠加的透明度

    Args:
        color1: 原始颜色
        color2: 变化后的颜色
        red (int): 红色值（0-255），默认为247

    Returns:
        float: 透明度（0-1）
    """
    return (color2[0] - color1[0]) / (red - color1[0])


def color_bar_percentage(image, area, prev_color, reverse=False, starter=0, threshold=30):
    """
    计算颜色条的百分比

    Args:
        image: 图像数组
        area: 区域
        prev_color: 上一个颜色
        reverse: 是否从右到左
        starter: 起始位置
        threshold: 阈值

    Returns:
        float: 百分比（0到1）
    """
    image = crop(image, area, copy=False)
    image = image[:, ::-1, :] if reverse else image
    length = image.shape[1]
    prev_index = starter

    for _ in range(1280):
        bar = color_similarity_2d(image, color=prev_color)
        index = np.where(np.any(bar > 255 - threshold, axis=0))[0]
        if not index.size:
            return prev_index / length
        else:
            index = index[-1]
        if index <= prev_index:
            return index / length
        prev_index = index

        prev_row = bar[:, prev_index] > 255 - threshold
        if not prev_row.size:
            return prev_index / length
        left = max(prev_index - 5, 0)
        mask = np.where(bar[:, left:prev_index + 1] > 255 - threshold)
        prev_color = np.mean(image[:, left:prev_index + 1][mask], axis=0)

    return 0.
