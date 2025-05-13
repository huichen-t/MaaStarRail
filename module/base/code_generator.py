# 导入必要的模块
import typing as t


class TabWrapper:
    """
    缩进包装器类，用于处理代码生成时的缩进
    支持上下文管理器协议，用于自动处理缩进
    """
    def __init__(self, generator, prefix='', suffix='', newline=True):
        """
        初始化缩进包装器

        Args:
            generator (CodeGenerator): 代码生成器实例
            prefix (str): 缩进块开始时的前缀
            suffix (str): 缩进块结束时的后缀
            newline (bool): 是否在添加前缀时换行
        """
        self.generator = generator
        self.prefix = prefix
        self.suffix = suffix
        self.newline = newline

        self.nested = False

    def __enter__(self):
        """进入缩进块时的处理"""
        if not self.nested and self.prefix:
            self.generator.add(self.prefix, newline=self.newline)
        self.generator.tab_count += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出缩进块时的处理"""
        self.generator.tab_count -= 1
        if self.suffix:
            self.generator.add(self.suffix)

    def __repr__(self):
        return self.prefix

    def set_nested(self, suffix=''):
        """
        设置为嵌套模式，用于处理嵌套的缩进块

        Args:
            suffix (str): 要添加的后缀
        """
        self.nested = True
        self.suffix += suffix


class VariableWrapper:
    """
    变量包装器类，用于处理代码生成时的变量名
    """
    def __init__(self, name):
        """
        初始化变量包装器

        Args:
            name: 变量名
        """
        self.name = name

    def __repr__(self):
        return str(self.name)

    __str__ = __repr__


class CodeGenerator:
    """
    代码生成器类，用于生成Python代码
    支持生成类、函数、变量、注释等代码结构
    """
    def __init__(self):
        """初始化代码生成器"""
        self.tab_count = 0  # 当前缩进级别
        self.lines = []     # 生成的代码行列表

    def add(self, line, comment=False, newline=True):
        """
        添加一行代码

        Args:
            line (str): 要添加的代码行
            comment (bool): 是否为注释行
            newline (bool): 是否在行尾添加换行符
        """
        self.lines.append(self._line_with_tabs(line, comment=comment, newline=newline))

    def generate(self):
        """
        生成完整的代码字符串

        Returns:
            str: 生成的代码
        """
        return ''.join(self.lines)

    def print(self):
        """打印生成的代码"""
        lines = self.generate()
        print(lines)

    def write(self, file: str = None):
        """
        将生成的代码写入文件

        Args:
            file (str): 目标文件路径
        """
        lines = self.generate()
        with open(file, 'w', encoding='utf-8', newline='') as f:
            f.write(lines)

    def _line_with_tabs(self, line, comment=False, newline=True):
        """
        为代码行添加缩进

        Args:
            line (str): 代码行
            comment (bool): 是否为注释行
            newline (bool): 是否添加换行符

        Returns:
            str: 处理后的代码行
        """
        if comment:
            line = '# ' + line
        out = '    ' * self.tab_count + line
        if newline:
            out += '\n'
        return out

    def _repr(self, obj):
        """
        获取对象的字符串表示

        Args:
            obj: 要处理的对象

        Returns:
            str: 对象的字符串表示
        """
        if isinstance(obj, str):
            if '\n' in obj:
                out = '"""\n'
                with self.tab():
                    for line in obj.strip().split('\n'):
                        line = line.strip()
                        out += self._line_with_tabs(line)
                out += self._line_with_tabs('"""', newline=False)
                return out
        return repr(obj)

    def tab(self):
        """
        创建新的缩进块

        Returns:
            TabWrapper: 缩进包装器实例
        """
        return TabWrapper(self)

    def Empty(self):
        """添加空行"""
        self.lines.append('\n')

    def Pass(self):
        """添加pass语句"""
        self.add('pass')

    def Import(self, text, empty=2):
        """
        添加导入语句

        Args:
            text (str): 导入语句文本
            empty (int): 导入语句后添加的空行数
        """
        for line in text.strip().split('\n'):
            line = line.strip()
            self.add(line)
        for _ in range(empty):
            self.Empty()

    def Variable(self, name):
        """
        创建变量

        Args:
            name: 变量名

        Returns:
            VariableWrapper: 变量包装器实例
        """
        return VariableWrapper(name)

    def Value(self, key=None, value=None, type_=None, **kwargs):
        """
        添加变量赋值语句

        Args:
            key: 变量名
            value: 变量值
            type_: 变量类型注解
            **kwargs: 其他变量赋值
        """
        if key is not None:
            if type_ is not None:
                self.add(f'{key}: {type_} = {self._repr(value)}')
            else:
                self.add(f'{key} = {self._repr(value)}')
        for key, value in kwargs.items():
            self.Value(key, value)

    def Comment(self, text):
        """
        添加注释

        Args:
            text (str): 注释文本
        """
        for line in text.strip().split('\n'):
            line = line.strip()
            self.add(line, comment=True)

    def CommentAutoGenerage(self, file):
        """
        添加自动生成文件的注释

        Args:
            file: 生成文件的模块路径，如 'dev_tools.button_extract'
        """
        # 只保留一个空行
        if len(self.lines) >= 2:
            if self.lines[-2:] == ['\n', '\n']:
                self.lines.pop(-1)
        self.Comment('This file was auto-generated, do not modify it manually. To generate:')
        self.Comment(f'``` python -m {file} ```')
        self.Empty()

    def List(self, key=None):
        """
        创建列表

        Args:
            key: 列表变量名

        Returns:
            TabWrapper: 列表缩进包装器
        """
        if key is not None:
            return TabWrapper(self, prefix=str(key) + ' = [', suffix=']')
        else:
            return TabWrapper(self, prefix='[', suffix=']')

    def ListItem(self, value):
        """
        添加列表项

        Args:
            value: 列表项值

        Returns:
            TabWrapper: 如果value是TabWrapper则返回它
        """
        if isinstance(value, TabWrapper):
            value.set_nested(suffix=',')
            self.add(f'{self._repr(value)}')
            return value
        else:
            self.add(f'{self._repr(value)},')

    def Dict(self, key=None):
        """
        创建字典

        Args:
            key: 字典变量名

        Returns:
            TabWrapper: 字典缩进包装器
        """
        if key is not None:
            return TabWrapper(self, prefix=str(key) + ' = {', suffix='}')
        else:
            return TabWrapper(self, prefix='{', suffix='}')

    def DictItem(self, key=None, value=None):
        """
        添加字典项

        Args:
            key: 键
            value: 值

        Returns:
            TabWrapper: 如果value是TabWrapper则返回它
        """
        if isinstance(value, TabWrapper):
            value.set_nested(suffix=',')
            if key is not None:
                self.add(f'{self._repr(key)}: {self._repr(value)}')
            return value
        else:
            if key is not None:
                self.add(f'{self._repr(key)}: {self._repr(value)},')

    def Object(self, object_class, key=None):
        """
        创建对象

        Args:
            object_class: 类名
            key: 对象变量名

        Returns:
            TabWrapper: 对象缩进包装器
        """
        if key is not None:
            return TabWrapper(self, prefix=f'{key} = {object_class}(', suffix=')')
        else:
            return TabWrapper(self, prefix=f'{object_class}(', suffix=')')

    def ObjectAttr(self, key=None, value=None):
        """
        添加对象属性

        Args:
            key: 属性名
            value: 属性值

        Returns:
            TabWrapper: 如果value是TabWrapper则返回它
        """
        if isinstance(value, TabWrapper):
            value.set_nested(suffix=',')
            if key is None:
                self.add(f'{self._repr(value)}')
            else:
                self.add(f'{key}={self._repr(value)}')
            return value
        else:
            if key is None:
                self.add(f'{self._repr(value)},')
            else:
                self.add(f'{key}={self._repr(value)},')

    def Class(self, name, inherit=None):
        """
        创建类定义

        Args:
            name: 类名
            inherit: 父类名

        Returns:
            TabWrapper: 类定义缩进包装器
        """
        if inherit is not None:
            return TabWrapper(self, prefix=f'class {name}({inherit}):')
        else:
            return TabWrapper(self, prefix=f'class {name}:')

    def Def(self, name, args=''):
        """
        创建函数定义

        Args:
            name: 函数名
            args: 函数参数

        Returns:
            TabWrapper: 函数定义缩进包装器
        """
        return TabWrapper(self, prefix=f'def {name}({args}):')


# 创建全局代码生成器实例
generator = CodeGenerator()
# 导出常用方法
Import = generator.Import
Value = generator.Value
Comment = generator.Comment
Dict = generator.Dict
DictItem = generator.DictItem


class MarkdownGenerator:
    """
    Markdown表格生成器类
    用于生成格式化的Markdown表格
    """
    def __init__(self, column: t.List[str]):
        """
        初始化Markdown生成器

        Args:
            column (List[str]): 表格的列标题列表
        """
        self.rows = [column]

    def add_row(self, row):
        """
        添加表格行

        Args:
            row: 行数据列表
        """
        self.rows.append([str(ele) for ele in row])

    def product_line(self, row, max_width):
        """
        生成表格行字符串

        Args:
            row: 行数据列表
            max_width: 每列的最大宽度列表

        Returns:
            str: 格式化后的表格行
        """
        row = [ele.ljust(width) for ele, width in zip(row, max_width)]
        row = ' | '.join(row)
        row = '| ' + row + ' |'
        return row

    def generate(self) -> t.List[str]:
        """
        生成完整的Markdown表格

        Returns:
            List[str]: 表格的每一行
        """
        import numpy as np
        # 计算每列的最大宽度
        width = np.array([
            [len(ele) for ele in row] for row in self.rows
        ])
        max_width = np.max(width, axis=0)
        # 生成分隔行
        dash = ['-' * width for width in max_width]

        # 生成完整的表格
        rows = [
            self.product_line(self.rows[0], max_width),  # 标题行
            self.product_line(dash, max_width),          # 分隔行
        ] + [
            self.product_line(row, max_width) for row in self.rows[1:]  # 数据行
        ]
        return rows
