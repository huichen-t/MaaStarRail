"""
日志记录模块，提供丰富的日志记录功能，包括控制台输出和文件记录。
支持富文本格式化、错误追踪、多级别日志等功能。
"""

import datetime
import logging
import os
import sys
from typing import Callable, List

from rich.console import Console, ConsoleOptions, ConsoleRenderable, NewLine
from rich.highlighter import NullHighlighter, RegexHighlighter
from rich.logging import RichHandler
from rich.rule import Rule
from rich.style import Style
from rich.theme import Theme
from rich.traceback import Traceback

# 配置标准输出和错误输出的编码为utf-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def empty_function(*args, **kwargs):
    """空函数，用于替换logging.basicConfig"""
    pass


# cnocr会设置root logger，为避免重复记录，删除logging.basicConfig
logging.basicConfig = empty_function
logging.raiseExceptions = True  # 设置为True以在控制台显示编码错误

# 移除HTTP关键词（GET, POST等）
RichHandler.KEYWORDS = []


class RichFileHandler(RichHandler):
    """富文本文件处理器，继承自RichHandler"""
    pass


class RichRenderableHandler(RichHandler):
    """
    富文本可渲染处理器，将日志记录转换为可渲染对象并传递给指定函数
    
    Args:
        func: 处理可渲染对象的回调函数
    """

    def __init__(self, *args, func: Callable[[ConsoleRenderable], None] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._func = func

    def emit(self, record: logging.LogRecord) -> None:
        """
        发送日志记录
        
        Args:
            record: 日志记录对象
        """
        message = self.format(record)
        traceback = None
        if (
                self.rich_tracebacks
                and record.exc_info
                and record.exc_info != (None, None, None)
        ):
            exc_type, exc_value, exc_traceback = record.exc_info
            assert exc_type is not None
            assert exc_value is not None
            traceback = Traceback.from_exception(
                exc_type,
                exc_value,
                exc_traceback,
                width=self.tracebacks_width,
                extra_lines=self.tracebacks_extra_lines,
                theme=self.tracebacks_theme,
                word_wrap=self.tracebacks_word_wrap,
                show_locals=self.tracebacks_show_locals,
                locals_max_length=self.locals_max_length,
                locals_max_string=self.locals_max_string,
            )
            message = record.getMessage()
            if self.formatter:
                record.message = record.getMessage()
                formatter = self.formatter
                if hasattr(formatter, "usesTime") and formatter.usesTime():
                    record.asctime = formatter.formatTime(
                        record, formatter.datefmt)
                message = formatter.formatMessage(record)

        message_renderable = self.render_message(record, message)
        log_renderable = self.render(
            record=record, traceback=traceback, message_renderable=message_renderable
        )

        # 直接将可渲染对象传递给函数
        self._func(log_renderable)

    def handle(self, record: logging.LogRecord) -> bool:
        """
        处理日志记录
        
        Args:
            record: 日志记录对象
            
        Returns:
            bool: 是否处理成功
        """
        if not self._func:
            return True
        super().handle(record)


class HTMLConsole(Console):
    """
    HTML控制台，强制使用完整功能
    但实际并未生效
    """

    @property
    def options(self) -> ConsoleOptions:
        """获取控制台选项"""
        return ConsoleOptions(
            max_height=self.size.height,
            size=self.size,
            legacy_windows=False,
            min_width=1,
            max_width=self.width,
            encoding='utf-8',
            is_terminal=False,
        )


class Highlighter(RegexHighlighter):
    """
    语法高亮器，用于高亮显示特定格式的文本
    """
    base_style = 'web.'
    highlights = [
        # 时间格式高亮
        (r'(?P<time>([0-1]{1}\d{1}|[2]{1}[0-3]{1})(?::)?'
         r'([0-5]{1}\d{1})(?::)?([0-5]{1}\d{1})(.\d+\b))'),
        # 括号高亮
        r"(?P<brace>[\{\[\(\)\]\}])",
        # 布尔值和None高亮
        r"\b(?P<bool_true>True)\b|\b(?P<bool_false>False)\b|\b(?P<none>None)\b",
        # 路径高亮
        r"(?P<path>(([A-Za-z]\:)|.)?\B([\/\\][\w\.\-\_\+]+)*[\/\\])(?P<filename>[\w\.\-\_\+]*)?",
    ]


# 定义Web主题样式
WEB_THEME = Theme({
    "web.brace": Style(bold=True),
    "web.bool_true": Style(color="bright_green", italic=True),
    "web.bool_false": Style(color="bright_red", italic=True),
    "web.none": Style(color="magenta", italic=True),
    "web.path": Style(color="magenta"),
    "web.filename": Style(color="bright_magenta"),
    "web.str": Style(color="green", italic=False, bold=False),
    "web.time": Style(color="cyan"),
    "rule.text": Style(bold=True),
})

# 初始化日志记录器
logger_debug = False
logger = logging.getLogger('alas')
logger.setLevel(logging.DEBUG if logger_debug else logging.INFO)

# 定义日志格式化器
file_formatter = logging.Formatter(
    fmt='%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_formatter = logging.Formatter(
    fmt='%(asctime)s.%(msecs)03d │ %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
web_formatter = logging.Formatter(
    fmt='%(asctime)s.%(msecs)03d │ %(message)s', datefmt='%H:%M:%S')

# 添加控制台日志处理器
stdout_console = console = Console()
console_hdlr = RichHandler(
    show_path=False,
    show_time=False,
    rich_tracebacks=True,
    tracebacks_show_locals=True,
    tracebacks_extra_lines=3,
)
console_hdlr.setFormatter(console_formatter)
logger.addHandler(console_hdlr)

# 确保在Alas根目录运行
os.chdir(os.path.join(os.path.dirname(__file__), '../../'))

# 获取当前脚本名称
pyw_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]


def _set_file_logger(name=pyw_name):
    """
    设置文件日志记录器（内部使用）
    
    Args:
        name: 日志文件名
    """
    if '_' in name:
        name = name.split('_', 1)[0]
    log_file = f'./log/{datetime.date.today()}_{name}.txt'
    try:
        file = logging.FileHandler(log_file, encoding='utf-8')
    except FileNotFoundError:
        os.mkdir('./log')
        file = logging.FileHandler(log_file, encoding='utf-8')
    file.setFormatter(file_formatter)

    logger.handlers = [h for h in logger.handlers if not isinstance(
        h, (logging.FileHandler, RichFileHandler))]
    logger.addHandler(file)
    logger.log_file = log_file


def set_file_logger(name=pyw_name):
    """
    设置文件日志记录器
    
    Args:
        name: 日志文件名
    """
    if '_' in name:
        name = name.split('_', 1)[0]
    log_file = f'./log/{datetime.date.today()}_{name}.txt'
    try:
        file = open(log_file, mode='a', encoding='utf-8')
    except FileNotFoundError:
        os.mkdir('./log')
        file = open(log_file, mode='a', encoding='utf-8')

    file_console = Console(
        file=file,
        no_color=True,
        highlight=False,
        width=119,
    )

    hdlr = RichFileHandler(
        console=file_console,
        show_path=False,
        show_time=False,
        show_level=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        tracebacks_extra_lines=3,
        highlighter=NullHighlighter(),
    )
    hdlr.setFormatter(file_formatter)

    logger.handlers = [h for h in logger.handlers if not isinstance(
        h, (logging.FileHandler, RichFileHandler))]
    logger.addHandler(hdlr)
    logger.log_file = log_file


def set_func_logger(func):
    """
    设置函数日志记录器
    
    Args:
        func: 处理日志记录的回调函数
    """
    console = HTMLConsole(
        force_terminal=False,
        force_interactive=False,
        width=80,
        color_system='truecolor',
        markup=False,
        safe_box=False,
        highlighter=Highlighter(),
        theme=WEB_THEME
    )
    hdlr = RichRenderableHandler(
        func=func,
        console=console,
        show_path=False,
        show_time=False,
        show_level=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        tracebacks_extra_lines=2,
        highlighter=Highlighter(),
    )
    hdlr.setFormatter(web_formatter)
    logger.handlers = [h for h in logger.handlers if not isinstance(
        h, RichRenderableHandler)]
    logger.addHandler(hdlr)


def _get_renderables(
        self: Console, *objects, sep=" ", end="\n", justify=None, emoji=None, markup=None, highlight=None,
) -> List[ConsoleRenderable]:
    """
    获取可渲染对象列表
    
    Args:
        *objects: 要渲染的对象
        sep: 分隔符
        end: 结束符
        justify: 对齐方式
        emoji: 是否使用emoji
        markup: 是否使用标记
        highlight: 是否高亮
        
    Returns:
        List[ConsoleRenderable]: 可渲染对象列表
    """
    if not objects:
        objects = (NewLine(),)

    render_hooks = self._render_hooks[:]
    with self:
        renderables = self._collect_renderables(
            objects,
            sep,
            end,
            justify=justify,
            emoji=emoji,
            markup=markup,
            highlight=highlight,
        )
        for hook in render_hooks:
            renderables = hook.process_renderables(renderables)
    return renderables


def print(*objects: ConsoleRenderable, **kwargs):
    """
    打印可渲染对象
    
    Args:
        *objects: 要打印的对象
        **kwargs: 其他参数
    """
    for hdlr in logger.handlers:
        if isinstance(hdlr, RichRenderableHandler):
            for renderable in _get_renderables(hdlr.console, *objects, **kwargs):
                hdlr._func(renderable)
        elif isinstance(hdlr, RichHandler):
            hdlr.console.print(*objects)


def rule(title="", *, characters="─", style="rule.line", end="\n", align="center"):
    """
    打印规则线
    
    Args:
        title: 标题
        characters: 使用的字符
        style: 样式
        end: 结束符
        align: 对齐方式
    """
    rule = Rule(title=title, characters=characters,
                style=style, end=end, align=align)
    print(rule)


def hr(title, level=3):
    """
    打印水平分隔线
    
    Args:
        title: 标题
        level: 级别（0-3）
    """
    title = str(title).upper()
    if level == 1:
        logger.rule(title, characters='═')
        logger.info(title)
    if level == 2:
        logger.rule(title, characters='─')
        logger.info(title)
    if level == 3:
        logger.info(f"[bold]<<< {title} >>>[/bold]", extra={"markup": True})
    if level == 0:
        logger.rule(characters='═')
        logger.rule(title, characters=' ')
        logger.rule(characters='═')


def attr(name, text):
    """
    打印属性
    
    Args:
        name: 属性名
        text: 属性值
    """
    logger.info('[%s] %s' % (str(name), str(text)))


def attr_align(name, text, front='', align=22):
    """
    打印对齐的属性
    
    Args:
        name: 属性名
        text: 属性值
        front: 前缀
        align: 对齐宽度
    """
    name = str(name).rjust(align)
    if front:
        name = front + name[len(front):]
    logger.info('%s: %s' % (name, str(text)))


def show():
    """显示所有日志级别的示例"""
    logger.info('INFO')
    logger.warning('WARNING')
    logger.debug('DEBUG')
    logger.error('ERROR')
    logger.critical('CRITICAL')
    logger.hr('hr0', 0)
    logger.hr('hr1', 1)
    logger.hr('hr2', 2)
    logger.hr('hr3', 3)
    logger.info(r'Brace { [ ( ) ] }')
    logger.info(r'True, False, None')
    logger.info(r'E:/path\\to/alas/alas.exe, /root/alas/, ./relative/path/log.txt')
    local_var1 = 'This is local variable'
    # 异常前的行
    raise Exception("Exception")
    # 异常后的行


def error_convert(func):
    """
    错误转换装饰器
    
    Args:
        func: 要装饰的函数
        
    Returns:
        装饰后的函数
    """
    def error_wrapper(msg, *args, **kwargs):
        if isinstance(msg, Exception):
            msg = f'{type(msg).__name__}: {msg}'
        return func(msg, *args, **kwargs)

    return error_wrapper


# 扩展logger对象的功能
logger.error = error_convert(logger.error)
logger.hr = hr
logger.attr = attr
logger.attr_align = attr_align
logger.set_file_logger = set_file_logger
logger.set_func_logger = set_func_logger
logger.rule = rule
logger.print = print
logger.log_file: str

# 初始化日志记录器
logger.set_file_logger()
logger.hr('Start', level=0)
