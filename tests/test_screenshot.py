"""
截图功能测试模块。
用于测试设备截图、图像处理等功能。
"""

import os
from datetime import datetime
from PIL import Image
import cv2

from module.device.device import Device
from module.base.utils.image_utils import crop, color_similarity_2d


class SimpleScreenshotTest:
    """
    简化版截图测试类。
    使用组合方式实现功能，降低耦合度。
    """
    
    def __init__(self):
        """
        初始化测试类。
        使用组合方式组织各个功能模块。
        """
        # 预设参数
        self.screenshot_method = 'uiautomator2'  # 截图方法
        self.control_method = 'uiautomator2'     # 控制方法
        self.device_serial = None                # 设备序列号，None表示自动检测
        
        # 组合各个功能模块
        self.device = Device(
            config=None,  # 不传入config
            serial=self.device_serial
        )
        
        # 创建screenshots目录
        if not os.path.exists('screenshots'):
            os.makedirs('screenshots')
    
    def test_screenshot(self):
        """
        测试基本截图功能。
        包括：
        1. 获取屏幕截图
        2. 保存截图
        3. 显示截图信息
        """
        print('开始测试截图功能')
        
        try:
            # 获取截图
            self.device.screenshot()
            print(f'截图尺寸: {self.device.image.shape}')
            
            # 保存截图
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'screenshots/screenshot_{timestamp}.png'
            
            # 保存图片
            Image.fromarray(self.device.image).save(filename)
            print(f'截图已保存至: {filename}')
            
            return filename
        except Exception as e:
            print(f'截图测试失败: {str(e)}')
            return None
        
    def test_crop(self, area=(100, 100, 300, 300)):
        """
        测试图像裁剪功能。
        
        Args:
            area (tuple): 裁剪区域 (x1, y1, x2, y2)
        """
        print('开始测试图像裁剪功能')
        
        try:
            # 获取截图
            self.device.screenshot()
            
            # 裁剪图像
            cropped = crop(self.device.image, area)
            print(f'裁剪后图像尺寸: {cropped.shape}')
            
            # 保存裁剪后的图像
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'screenshots/cropped_{timestamp}.png'
            
            Image.fromarray(cropped).save(filename)
            print(f'裁剪图像已保存至: {filename}')
            
            return filename
        except Exception as e:
            print(f'裁剪测试失败: {str(e)}')
            return None
        
    def test_color_detection(self, area=(100, 100, 300, 300), color=(255, 255, 255)):
        """
        测试颜色检测功能。
        
        Args:
            area (tuple): 检测区域 (x1, y1, x2, y2)
            color (tuple): 目标颜色 (R, G, B)
        """
        print('开始测试颜色检测功能')
        
        try:
            # 获取截图
            self.device.screenshot()
            
            # 裁剪区域
            image = crop(self.device.image, area)
            
            # 检测颜色
            mask = color_similarity_2d(image, color=color)
            cv2.inRange(mask, 221, 255, dst=mask)
            count = cv2.countNonZero(mask)
            
            print(f'检测到目标颜色的像素数量: {count}')
            return count
        except Exception as e:
            print(f'颜色检测测试失败: {str(e)}')
            return None
        
    def run_all_tests(self):
        """
        运行所有测试。
        """
        print('开始运行所有测试')
        
        results = {
            'screenshot': None,
            'cropped': None,
            'color_count': None
        }
        
        # 测试基本截图
        results['screenshot'] = self.test_screenshot()
        
        # 测试图像裁剪
        results['cropped'] = self.test_crop()
        
        # 测试颜色检测
        results['color_count'] = self.test_color_detection()
        
        print('所有测试完成')
        return results


def main():
    """
    主函数，用于直接运行测试。
    """
    # 创建测试实例
    test = SimpleScreenshotTest()
    a = Device('src')
    a.screenshot()
    # 运行测试
    results = test.run_all_tests()

    # 打印结果
    print('\n测试结果:')
    print(f'截图文件: {results["screenshot"]}')
    print(f'裁剪文件: {results["cropped"]}')
    print(f'颜色检测结果: {results["color_count"]}')


if __name__ == '__main__':
    main() 