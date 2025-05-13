import cv2

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
