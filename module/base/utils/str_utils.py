
def float2str(n, decimal=3):
    """
    将浮点数转换为字符串

    Args:
        n (float): 浮点数
        decimal (int): 小数位数

    Returns:
        str: 格式化后的字符串
    """
    return str(round(n, decimal)).ljust(decimal + 2, "0")


def point2str(x, y, length=4):
    """
    将点坐标转换为字符串

    Args:
        x (int, float): x坐标
        y (int, float): y坐标
        length (int): 对齐长度

    Returns:
        str: 格式化后的字符串，如 '( 100,  80)'
    """
    return '(%s, %s)' % (str(int(x)).rjust(length), str(int(y)).rjust(length))

