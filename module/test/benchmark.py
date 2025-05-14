"""
性能测试模块，用于测试和评估不同截图和控制方法的性能。
"""

import time
import typing as t

import numpy as np
from rich.table import Table
from rich.text import Text

from module.base.utils import float2str as float2str_
from module.base.utils import random_rectangle_point
from module.core.daemon_base import DaemonBase
from module.exception import RequestHumanTakeover
from module.logger import logger


def float2str(n, decimal=3):
    """
    将浮点数转换为字符串，添加时间单位
    
    Args:
        n: 要转换的数值
        decimal: 小数位数
        
    Returns:
        str: 格式化后的字符串，带时间单位
    """
    if not isinstance(n, (float, int)):
        return str(n)
    else:
        return float2str_(n, decimal=decimal) + 's'


class Benchmark(DaemonBase):
    """
    性能测试类，用于测试不同截图和控制方法的性能
    """
    TEST_TOTAL = 15  # 总测试次数
    TEST_BEST = int(TEST_TOTAL * 0.8)  # 取最好的80%结果

    def benchmark_test(self, func, *args, **kwargs):
        """
        执行性能测试
        
        Args:
            func: 要测试的函数
            *args: 传递给func的位置参数
            **kwargs: 传递给func的关键字参数

        Returns:
            float: 平均耗时
        """
        logger.hr(f'Benchmark test', level=2)
        logger.info(f'Testing function: {func.__name__}')
        record = []

        for n in range(1, self.TEST_TOTAL + 1):
            start = time.time()

            try:
                func(*args, **kwargs)
            except RequestHumanTakeover:
                logger.critical('RequestHumanTakeover')
                logger.warning(f'Benchmark tests failed on func: {func.__name__}')
                return 'Failed'
            except Exception as e:
                logger.exception(e)
                logger.warning(f'Benchmark tests failed on func: {func.__name__}')
                return 'Failed'

            cost = time.time() - start
            logger.attr(
                f'{str(n).rjust(2, "0")}/{self.TEST_TOTAL}',
                f'{float2str(cost)}'
            )
            record.append(cost)

        logger.info('Benchmark tests done')
        average = float(np.mean(np.sort(record)[:self.TEST_BEST]))
        logger.info(f'Time cost {float2str(average)} ({self.TEST_BEST} best results out of {self.TEST_TOTAL} tests)')
        return average

    @staticmethod
    def evaluate_screenshot(cost):
        """
        评估截图性能
        
        Args:
            cost: 耗时

        Returns:
            Text: 带颜色的性能评估文本
        """
        if not isinstance(cost, (float, int)):
            return Text(cost, style="bold bright_red")

        if cost < 0.025:
            return Text('Insane Fast', style="bold bright_green")
        if cost < 0.100:
            return Text('Ultra Fast', style="bold bright_green")
        if cost < 0.200:
            return Text('Very Fast', style="bright_green")
        if cost < 0.300:
            return Text('Fast', style="green")
        if cost < 0.500:
            return Text('Medium', style="yellow")
        if cost < 0.750:
            return Text('Slow', style="red")
        if cost < 1.000:
            return Text('Very Slow', style="bright_red")
        return Text('Ultra Slow', style="bold bright_red")

    @staticmethod
    def evaluate_click(cost):
        """
        评估点击性能
        
        Args:
            cost: 耗时

        Returns:
            Text: 带颜色的性能评估文本
        """
        if not isinstance(cost, (float, int)):
            return Text(cost, style="bold bright_red")

        if cost < 0.100:
            return Text('Fast', style="bright_green")
        if cost < 0.200:
            return Text('Medium', style="yellow")
        if cost < 0.400:
            return Text('Slow', style="red")
        return Text('Very Slow', style="bright_red")

    @staticmethod
    def show(test, data, evaluate_func):
        """
        显示性能测试结果表格
        
        Args:
            test: 测试类型（Screenshot/Control）
            data: 测试数据
            evaluate_func: 评估函数
        """
        table = Table(show_lines=True)
        table.add_column(
            test, header_style="bright_cyan", style="cyan", no_wrap=True
        )
        table.add_column("Time", style="magenta")
        table.add_column("Speed", style="green")
        for row in data:
            table.add_row(
                row[0],
                float2str(row[1]),
                evaluate_func(row[1]),
            )
        logger.print(table, justify='center')

    def benchmark(self, screenshot: t.Tuple[str] = (), click: t.Tuple[str] = ()):
        """
        执行性能测试
        
        Args:
            screenshot: 要测试的截图方法列表
            click: 要测试的点击方法列表
            
        Returns:
            tuple: (最快的截图方法, 最快的点击方法)
        """
        logger.hr('Benchmark', level=1)
        logger.info(f'Testing screenshot methods: {screenshot}')
        logger.info(f'Testing click methods: {click}')

        # 测试截图方法
        screenshot_result = []
        for method in screenshot:
            result = self.benchmark_test(self.device.screenshot_methods[method])
            screenshot_result.append([method, result])

        # 测试点击方法
        area = (124, 4, 649, 106)  # 安全点击区域
        click_result = []
        for method in click:
            x, y = random_rectangle_point(area)
            result = self.benchmark_test(self.device.click_methods[method], x, y)
            click_result.append([method, result])

        def compare(res):
            """比较性能结果"""
            res = res[1]
            if not isinstance(res, (int, float)):
                return 100
            else:
                return res

        logger.hr('Benchmark Results', level=1)
        fastest_screenshot = 'ADB_nc'
        fastest_click = 'minitouch'
        
        # 显示截图测试结果
        if screenshot_result:
            self.show(test='Screenshot', data=screenshot_result, evaluate_func=self.evaluate_screenshot)
            fastest = sorted(screenshot_result, key=lambda item: compare(item))[0]
            logger.info(f'Recommend screenshot method: {fastest[0]} ({float2str(fastest[1])})')
            fastest_screenshot = fastest[0]
            
        # 显示点击测试结果
        if click_result:
            self.show(test='Control', data=click_result, evaluate_func=self.evaluate_click)
            fastest = sorted(click_result, key=lambda item: compare(item))[0]
            # 如果minitouch和MaaTouch都是最快的，优先选择MaaTouch
            if 'MaaTouch' in click and fastest[0] == 'minitouch':
                fastest[0] = 'MaaTouch'
            logger.info(f'Recommend control method: {fastest[0]} ({float2str(fastest[1])})')
            fastest_click = fastest[0]

        return fastest_screenshot, fastest_click

    def get_test_methods(self) -> t.Tuple[t.Tuple[str], t.Tuple[str]]:
        """
        获取要测试的方法列表
        
        Returns:
            tuple: (截图方法列表, 点击方法列表)
        """
        device = 'emulator'
        screenshot = ['ADB', 'ADB_nc', 'uiautomator2', 'aScreenCap', 'aScreenCap_nc', 'DroidCast', 'DroidCast_raw']
        click = ['ADB', 'uiautomator2', 'minitouch', 'MaaTouch']

        def remove(*args):
            """从列表中移除指定项"""
            return [l for l in screenshot if l not in args]

        # 根据Android SDK版本移除不支持的方法
        sdk = self.device.sdk_ver
        logger.info(f'sdk_ver: {sdk}')
        if not (21 <= sdk <= 28):
            screenshot = remove('aScreenCap', 'aScreenCap_nc')
        # 移除不支持nc回环的方法
        if device in ['plone_cloud_with_adb']:
            screenshot = remove('ADB_nc', 'aScreenCap_nc')
        # VMOS特殊处理
        if device == 'android_phone_vmos':
            screenshot = ['ADB', 'aScreenCap', 'DroidCast', 'DroidCast_raw']
            click = ['ADB', 'Hermit', 'MaaTouch']
            
        # 添加特殊设备支持的方法
        if self.device.nemu_ipc_available():
            screenshot.append('nemu_ipc')
        if self.device.ldopengl_available():
            screenshot.append('ldopengl')

        scene = 'screenshot_click'
        if 'screenshot' not in scene:
            screenshot = []
        if 'click' not in scene:
            click = []

        return tuple(screenshot), tuple(click)

    def run(self):
        """运行性能测试"""
        try:
            self.config.override(Emulator_ScreenshotMethod='ADB')
            self.device.uninstall_minicap()
        except RequestHumanTakeover:
            logger.critical('Request human takeover')
            return

        screenshot, click = self.get_test_methods()
        self.benchmark(screenshot, click)

    def run_simple_screenshot_benchmark(self):
        """
        运行简单的截图性能测试
        
        Returns:
            str: 当前设备上最快的截图方法
        """
        screenshot = ['ADB', 'ADB_nc', 'uiautomator2', 'aScreenCap', 'aScreenCap_nc', 'DroidCast', 'DroidCast_raw']

        def remove(*args):
            return [l for l in screenshot if l not in args]

        # 根据设备特性选择可用的截图方法
        sdk = self.device.sdk_ver
        logger.info(f'sdk_ver: {sdk}')
        if not (21 <= sdk <= 28):
            screenshot = remove('aScreenCap', 'aScreenCap_nc')
        if self.device.is_chinac_phone_cloud:
            screenshot = remove('ADB_nc', 'aScreenCap_nc')
        if self.device.nemu_ipc_available():
            screenshot.append('nemu_ipc')
        if self.device.ldopengl_available():
            screenshot.append('ldopengl')
        screenshot = tuple(screenshot)

        # 减少测试次数以加快测试速度
        self.TEST_TOTAL = 3
        self.TEST_BEST = 1
        method, _ = self.benchmark(screenshot, tuple())

        return method


def run_benchmark(config):
    """
    运行性能测试的入口函数
    
    Args:
        config: 配置对象
        
    Returns:
        bool: 测试是否成功
    """
    try:
        Benchmark(config, task='Benchmark').run()
        return True
    except RequestHumanTakeover:
        logger.critical('Request human takeover')
        return False


if __name__ == '__main__':
    b = Benchmark('src', task='Benchmark')
    b.run()
