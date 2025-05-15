"""
控制器测试模块。
提供测试各种控制器功能和性能的方法。
"""
import time
import argparse
from typing import Dict
import numpy as np
from module.config import Config
from module.device.controllers import *
from module.base.logger import logger


class ControllerTester:
    """
    控制器测试类。
    用于测试各种控制器的功能和性能。
    """
    
    def __init__(self, config):
        """
        初始化测试器。
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.controllers: Dict[str, DeviceController] = {}
        self.test_results: Dict[str, Dict[str, bool]] = {}
        self.benchmark_results: Dict[str, Dict[str, float]] = {}
        self.iterations = 10  # 性能测试的迭代次数
        
    def init_controllers(self, controllers=None) -> None:
        """
        初始化控制器。
        
        Args:
            controllers: 要初始化的控制器列表，None表示初始化所有控制器
        """
        controller_classes = {
            'adb': AdbController,
            'uiautomator': UiautomatorController,
            'minitouch': MinitouchController,
            'hermit': HermitController,
            'maatouch': MaaTouchController,
            'nemu': NemuController,
            'scrcpy': ScrcpyController
        }
        
        if controllers:
            # 只初始化指定的控制器
            for name in controllers:
                if name in controller_classes:
                    try:
                        controller = controller_classes[name](self.config)
                        if controller.connect():
                            self.controllers[name] = controller
                            logger.info(f'Successfully initialized {name} controller')
                        else:
                            logger.warning(f'Failed to initialize {name} controller')
                    except Exception as e:
                        logger.error(f'Error initializing {name} controller: {e}')
        else:
            # 初始化所有控制器
            for name, cls in controller_classes.items():
                try:
                    controller = cls(self.config)
                    if controller.connect():
                        self.controllers[name] = controller
                        logger.info(f'Successfully initialized {name} controller')
                    else:
                        logger.warning(f'Failed to initialize {name} controller')
                except Exception as e:
                    logger.error(f'Error initializing {name} controller: {e}')
                    
    def test_basic_operations(self, controller: DeviceController) -> Dict[str, bool]:
        """
        测试基本操作。
        
        Args:
            controller: 要测试的控制器
            
        Returns:
            Dict[str, bool]: 测试结果
        """
        results = {}
        
        # 测试点击
        try:
            controller.click(100, 100)
            time.sleep(0.5)
            results['click'] = True
        except Exception as e:
            logger.error(f'Click test failed: {e}')
            results['click'] = False
            
        # 测试长按
        try:
            controller.long_click(200, 200, 0.5)
            time.sleep(0.5)
            results['long_click'] = True
        except Exception as e:
            logger.error(f'Long click test failed: {e}')
            results['long_click'] = False
            
        # 测试滑动
        try:
            controller.swipe(300, 300, 400, 400, 0.5)
            time.sleep(0.5)
            results['swipe'] = True
        except Exception as e:
            logger.error(f'Swipe test failed: {e}')
            results['swipe'] = False
            
        # 测试截图
        try:
            image = controller.screenshot()
            results['screenshot'] = isinstance(image, np.ndarray)
        except Exception as e:
            logger.error(f'Screenshot test failed: {e}')
            results['screenshot'] = False
            
        # 测试分辨率获取
        try:
            width, height = controller.get_resolution()
            results['resolution'] = isinstance(width, int) and isinstance(height, int)
        except Exception as e:
            logger.error(f'Resolution test failed: {e}')
            results['resolution'] = False
            
        return results
        
    def benchmark_click(self, controller: DeviceController) -> float:
        """
        测试点击操作的性能。
        
        Args:
            controller: 要测试的控制器
            
        Returns:
            float: 平均执行时间（毫秒）
        """
        times = []
        for _ in range(self.iterations):
            start = time.time()
            controller.click(100, 100)
            end = time.time()
            times.append((end - start) * 1000)  # 转换为毫秒
            time.sleep(0.1)  # 避免操作过快
        return sum(times) / len(times)
        
    def benchmark_long_click(self, controller: DeviceController) -> float:
        """
        测试长按操作的性能。
        
        Args:
            controller: 要测试的控制器
            
        Returns:
            float: 平均执行时间（毫秒）
        """
        times = []
        for _ in range(self.iterations):
            start = time.time()
            controller.long_click(200, 200, 0.5)
            end = time.time()
            times.append((end - start) * 1000)
            time.sleep(0.1)
        return sum(times) / len(times)
        
    def benchmark_swipe(self, controller: DeviceController) -> float:
        """
        测试滑动操作的性能。
        
        Args:
            controller: 要测试的控制器
            
        Returns:
            float: 平均执行时间（毫秒）
        """
        times = []
        for _ in range(self.iterations):
            start = time.time()
            controller.swipe(300, 300, 400, 400, 0.5)
            end = time.time()
            times.append((end - start) * 1000)
            time.sleep(0.1)
        return sum(times) / len(times)
        
    def benchmark_screenshot(self, controller: DeviceController) -> float:
        """
        测试截图操作的性能。
        
        Args:
            controller: 要测试的控制器
            
        Returns:
            float: 平均执行时间（毫秒）
        """
        times = []
        for _ in range(self.iterations):
            start = time.time()
            controller.screenshot()
            end = time.time()
            times.append((end - start) * 1000)
            time.sleep(0.1)
        return sum(times) / len(times)
        
    def benchmark_resolution(self, controller: DeviceController) -> float:
        """
        测试获取分辨率操作的性能。
        
        Args:
            controller: 要测试的控制器
            
        Returns:
            float: 平均执行时间（毫秒）
        """
        times = []
        for _ in range(self.iterations):
            start = time.time()
            controller.get_resolution()
            end = time.time()
            times.append((end - start) * 1000)
            time.sleep(0.1)
        return sum(times) / len(times)
        
    def run_function_tests(self) -> None:
        """
        运行功能测试。
        """
        for name, controller in self.controllers.items():
            logger.info(f'Testing {name} controller...')
            self.test_results[name] = self.test_basic_operations(controller)
            
    def run_performance_tests(self) -> None:
        """
        运行性能测试。
        """
        for name, controller in self.controllers.items():
            logger.info(f'Benchmarking {name} controller...')
            self.benchmark_results[name] = {
                'click': self.benchmark_click(controller),
                'long_click': self.benchmark_long_click(controller),
                'swipe': self.benchmark_swipe(controller),
                'screenshot': self.benchmark_screenshot(controller),
                'resolution': self.benchmark_resolution(controller)
            }
            
    def print_function_results(self) -> None:
        """
        打印功能测试结果。
        """
        logger.info('Function Test Results:')
        for name, results in self.test_results.items():
            logger.info(f'\n{name} controller:')
            for operation, success in results.items():
                status = '✓' if success else '✗'
                logger.info(f'  {operation}: {status}')
                
    def print_performance_results(self) -> None:
        """
        打印性能测试结果。
        """
        logger.info('Performance Test Results (ms):')
        for name, results in self.benchmark_results.items():
            logger.info(f'\n{name} controller:')
            for operation, time_ms in results.items():
                logger.info(f'  {operation}: {time_ms:.2f}ms')
                
    def cleanup(self) -> None:
        """
        清理资源。
        """
        for controller in self.controllers.values():
            controller.release()


def parse_args():
    """
    解析命令行参数。
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description='运行控制器测试')
    parser.add_argument('--type', type=str, choices=['function', 'performance', 'all'],
                      default='all', help='测试类型：功能测试、性能测试或全部')
    parser.add_argument('--controller', type=str, nargs='+',
                      help='要测试的控制器列表，不指定则测试所有控制器')
    return parser.parse_args()


def main():
    """
    主函数。
    """
    args = parse_args()
    config = Config()
    
    tester = ControllerTester(config)
    tester.init_controllers(args.controller)
    
    if args.type in ['function', 'all']:
        tester.run_function_tests()
        tester.print_function_results()
        
    if args.type in ['performance', 'all']:
        tester.run_performance_tests()
        tester.print_performance_results()
        
    tester.cleanup()


if __name__ == '__main__':
    main() 