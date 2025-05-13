"""
日志模块的类型提示存根文件。
提供类型声明，用于IDE代码补全和类型检查。
"""

import logging
from typing import Any, Callable

from rich.console import Console, ConsoleRenderable
from rich.highlighter import RegexHighlighter
from rich.logging import RichHandler
from rich.theme import Theme

class HTMLConsole(Console):
    """
    HTML控制台类，继承自rich.console.Console
    用于在HTML环境中显示富文本内容
    """
    ...

class Highlighter(RegexHighlighter):
    """
    语法高亮器类，继承自rich.highlighter.RegexHighlighter
    用于高亮显示特定格式的文本
    """
    ...

# 全局变量声明
WEB_THEME: Theme  # Web主题样式配置
logger_debug: bool  # 是否启用调试模式
pyw_name: str  # 当前脚本名称

# 日志格式化器声明
file_formatter: logging.Formatter  # 文件日志格式化器
console_formatter: logging.Formatter  # 控制台日志格式化器
web_formatter: logging.Formatter  # Web日志格式化器

# 控制台相关变量声明
stdout_console: Console  # 标准输出控制台
console_hdlr: RichHandler  # 富文本控制台处理器

def set_file_logger(
    name: str = pyw_name,
) -> None:
    """
    设置文件日志记录器
    
    Args:
        name: 日志文件名，默认为当前脚本名称
    """
    ...

def set_func_logger(
    func: Callable[[ConsoleRenderable], None],
) -> None:
    """
    设置函数日志记录器
    
    Args:
        func: 处理日志记录的回调函数，接收ConsoleRenderable类型参数
    """
    ...

class __logger(logging.Logger):
    """
    自定义日志记录器类，继承自logging.Logger
    扩展了标准日志记录器的功能
    """
    
    def rule(
        self,
        title: str = "",
        *,
        characters: str = "-",
        style: str = "rule.line",
        end: str = "\n",
        align: str = "center",
    ) -> None:
        """
        打印规则线
        
        Args:
            title: 规则线标题
            characters: 使用的字符
            style: 样式
            end: 结束符
            align: 对齐方式
        """
        ...

    def hr(
        self,
        title,
        level: int = 3,
    ) -> None:
        """
        打印水平分隔线
        
        Args:
            title: 分隔线标题
            level: 分隔线级别（0-3）
        """
        ...

    def attr(
        self,
        name,
        text,
    ) -> None:
        """
        打印属性
        
        Args:
            name: 属性名
            text: 属性值
        """
        ...

    def attr_align(
        self,
        name,
        text,
        front="",
        align: int = 22,
    ) -> None:
        """
        打印对齐的属性
        
        Args:
            name: 属性名
            text: 属性值
            front: 前缀
            align: 对齐宽度
        """
        ...

    def set_file_logger(
        self,
        name: str = pyw_name,
    ) -> None:
        """
        设置文件日志记录器
        
        Args:
            name: 日志文件名，默认为当前脚本名称
        """
        ...

    def set_func_logger(
        self,
        func: Callable[[ConsoleRenderable], None],
    ) -> None:
        """
        设置函数日志记录器
        
        Args:
            func: 处理日志记录的回调函数，接收ConsoleRenderable类型参数
        """
        ...

    def print(
        self,
        *objects: ConsoleRenderable,
        **kwargs,
    ) -> None:
        """
        打印可渲染对象
        
        Args:
            *objects: 要打印的可渲染对象
            **kwargs: 其他参数
        """
        ...

# 全局日志记录器实例
logger: __logger  # 自定义日志记录器实例，用于整个应用程序的日志记录
