def handle_sensitive_image(image):
    """
    处理图像中的敏感信息
    将图像中的UID区域（左上角）涂黑以保护隐私

    Args:
        image (np.ndarray): 需要处理的图像数组

    Returns:
        np.ndarray: 处理后的图像数组，UID区域已被涂黑
    """
    # 将UID区域（坐标范围：x=0-180, y=680-720）涂黑
    image[680:720, 0:180, :] = 0
    return image


def handle_sensitive_logs(logs):
    """
    处理日志中的敏感信息
    目前为占位函数，可以根据需要添加日志脱敏逻辑

    Args:
        logs (str): 需要处理的日志内容

    Returns:
        str: 处理后的日志内容
    """
    return logs
