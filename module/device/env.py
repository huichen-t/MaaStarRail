"""
环境变量定义模块。
用于判断当前运行环境的操作系统类型。
这些变量在程序运行时会根据不同的操作系统平台自动设置。
"""

import sys

# 判断是否为Windows系统
# 当sys.platform为'win32'时表示Windows系统
IS_WINDOWS = sys.platform == 'win32'

# 判断是否为MacOS系统
# 当sys.platform为'darwin'时表示MacOS系统
IS_MACINTOSH = sys.platform == 'darwin'

# 判断是否为Linux系统
# 当sys.platform为'linux'时表示Linux系统
IS_LINUX = sys.platform == 'linux'
