"""
游戏界面开关状态管理模块。
提供统一的接口来处理游戏中的各种开关状态切换，支持重试机制。
"""

from module.base.base import ModuleBase
from module.base.timer import Timer
from module.exception import ScriptError
from module.logger import logger


class Switch:
    """
    游戏界面开关状态管理类。
    用于处理游戏中的各种开关状态切换，支持状态检测和自动重试。
    
    示例：
        # 定义开关
        submarine_hunt = Switch('Submarine_hunt', offset=120)
        submarine_hunt.add_state('on', check_button=SUBMARINE_HUNT_ON)
        submarine_hunt.add_state('off', check_button=SUBMARINE_HUNT_OFF)

        # 切换到ON状态
        submarine_view.set('on', main=self)
    """

    def __init__(self, name='Switch', is_selector=False):
        """
        初始化开关状态管理器。
        
        Args:
            name (str): 开关名称，用于日志输出
            is_selector (bool): 是否为选择器类型
                - True: 多选类型，点击后会在不同选项间切换
                  例如: | [每日] | 紧急 | -> 点击 -> | 每日 | [紧急] |
                - False: 开关类型，点击同一位置切换状态
                  例如: | [开启] | -> 点击 -> | [关闭] |
        """
        self.name = name
        self.is_selector = is_selector
        self.state_list = []

    def add_state(self, state, check_button, click_button=None):
        """
        添加一个状态到状态列表。
        
        Args:
            state (str): 状态名称，不能使用'unknown'作为状态名
            check_button (ButtonWrapper): 用于检测该状态的按钮
            click_button (ButtonWrapper): 用于切换到该状态的按钮，默认与check_button相同
        """
        if state == 'unknown':
            raise ScriptError(f'Cannot use "unknown" as state name')
        self.state_list.append({
            'state': state,
            'check_button': check_button,
            'click_button': click_button if click_button is not None else check_button,
        })

    def appear(self, main):
        """
        检查开关是否出现在屏幕上。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            bool: 开关是否可见
        """
        for data in self.state_list:
            if main.appear(data['check_button']):
                return True
        return False

    def get(self, main):
        """
        获取当前开关状态。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            str: 当前状态名称，如果无法识别则返回'unknown'
        """
        for data in self.state_list:
            if main.appear(data['check_button']):
                return data['state']
        return 'unknown'

    def click(self, state, main):
        """
        点击指定状态的按钮。
        
        Args:
            state (str): 目标状态
            main (ModuleBase): 主模块实例
        """
        button = self.get_data(state)['click_button']
        main.device.click(button)

    def get_data(self, state):
        """
        获取指定状态的配置数据。
        
        Args:
            state (str): 状态名称
            
        Returns:
            dict: 状态配置数据
            
        Raises:
            ScriptError: 当状态无效时抛出异常
        """
        for row in self.state_list:
            if row['state'] == state:
                return row
        raise ScriptError(f'Switch {self.name} received an invalid state: {state}')

    def handle_additional(self, main):
        """
        处理额外的弹窗或界面元素。
        子类可以重写此方法来实现特定的处理逻辑。
        
        Args:
            main (ModuleBase): 主模块实例
            
        Returns:
            bool: 是否处理了额外元素
        """
        return False

    def set(self, state, main, skip_first_screenshot=True):
        """
        将开关设置到指定状态。
        
        工作流程：
        1. 检测当前状态
        2. 如果当前状态不是目标状态，则点击切换
        3. 处理可能出现的额外弹窗
        4. 重试直到达到目标状态或超时
        
        Args:
            state (str): 目标状态
            main (ModuleBase): 主模块实例
            skip_first_screenshot (bool): 是否跳过第一次截图
            
        Returns:
            bool: 是否进行了点击操作
        """
        logger.info(f'{self.name} set to {state}')
        self.get_data(state)

        changed = False
        has_unknown = False
        unknown_timer = Timer(5, count=10).start()
        click_timer = Timer(1, count=3)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                main.device.screenshot()

            # 检测当前状态
            current = self.get(main=main)
            logger.attr(self.name, current)

            # 达到目标状态，退出
            if current == state:
                return changed

            # 处理额外弹窗
            if self.handle_additional(main=main):
                continue

            # 处理未知状态
            if current == 'unknown':
                if unknown_timer.reached():
                    logger.warning(f'Switch {self.name} has states evaluated to unknown, '
                                   f'asset should be re-verified')
                    has_unknown = True
                    unknown_timer.reset()
                # 如果未知状态计时器未触发，不点击（可能是切换动画）
                # 如果未知状态计时器已触发，点击目标状态（可能是新状态）
                if not has_unknown:
                    continue
            else:
                # 已知状态，重置计时器
                unknown_timer.reset()

            # 执行点击
            if click_timer.reached():
                if self.is_selector:
                    # 选择器类型：点击目标状态
                    click_state = state
                else:
                    # 开关类型：如果当前是未知状态，点击目标状态
                    # 否则点击当前状态来切换
                    if current == 'unknown':
                        click_state = state
                    else:
                        click_state = current
                self.click(click_state, main=main)
                changed = True
                click_timer.reset()
                unknown_timer.reset()

        return changed

    def wait(self, main, skip_first_screenshot=True):
        """
        等待直到任何状态被激活。
        
        Args:
            main (ModuleBase): 主模块实例
            skip_first_screenshot (bool): 是否跳过第一次截图
            
        Returns:
            bool: 是否成功等待到状态激活
        """
        timeout = Timer(2, count=6).start()
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                main.device.screenshot()

            # 检测当前状态
            current = self.get(main=main)
            logger.attr(self.name, current)

            # 状态已激活或超时
            if current != 'unknown':
                return True
            if timeout.reached():
                logger.warning(f'{self.name} wait activated timeout')
                return False

            # 处理额外弹窗
            if self.handle_additional(main=main):
                continue
