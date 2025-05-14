"""
深层字典操作模块，提供了一系列用于处理嵌套字典和列表的函数。
这些函数针对高性能进行了优化，因此代码可能看起来比较复杂。
在性能实践中，时间成本如下：
- 当键存在时：
  try: dict[key] except KeyError << dict.get(key) < if key in dict: dict[key]
- 当键不存在时：
  if key in dict: dict[key] < dict.get(key) <<< try: dict[key] except KeyError
"""

from collections import deque

# 操作类型常量
OP_ADD = 'add'  # 添加操作
OP_SET = 'set'  # 设置操作
OP_DEL = 'del'  # 删除操作


def deep_get(d, keys, default=None):
    """
    从嵌套字典和列表中安全地获取值
    
    Args:
        d (dict): 要查询的字典
        keys (list[str], str): 键路径，如 ['Scheduler', 'NextRun', 'value']
        default: 当键不存在时返回的默认值

    Returns:
        指定键路径上的值，如果不存在则返回默认值
    """
    # 性能：240 + 30 * 深度 (纳秒)
    if type(keys) is str:
        keys = keys.split('.')

    try:
        for k in keys:
            d = d[k]
        return d
    except KeyError:  # 键不存在
        return default
    except IndexError:  # 键不存在
        return default
    except TypeError:  # 输入keys不可迭代或d不是字典
        return default


def deep_get_with_error(d, keys):
    """
    从嵌套字典和列表中获取值，如果键不存在则抛出KeyError
    
    Args:
        d (dict): 要查询的字典
        keys (list[str], str): 键路径，如 ['Scheduler', 'NextRun', 'value']

    Returns:
        指定键路径上的值

    Raises:
        KeyError: 当键不存在时抛出
    """
    # 性能：240 + 30 * 深度 (纳秒)
    if type(keys) is str:
        keys = keys.split('.')

    try:
        for k in keys:
            d = d[k]
        return d
    except IndexError:  # 键不存在
        raise KeyError
    except TypeError:  # 输入keys不可迭代或d不是字典
        raise KeyError


def deep_exist(d, keys):
    """
    检查嵌套字典或列表中是否存在指定的键路径
    
    Args:
        d (dict): 要查询的字典
        keys (str, list): 键路径，如 'Scheduler.NextRun.value'

    Returns:
        bool: 如果键路径存在返回True，否则返回False
    """
    # 性能：240 + 30 * 深度 (纳秒)
    if type(keys) is str:
        keys = keys.split('.')

    try:
        for k in keys:
            d = d[k]
        return True
    except KeyError:  # 键不存在
        return False
    except IndexError:  # 键不存在
        return False
    except TypeError:  # 输入keys不可迭代或d不是字典
        return False


def deep_set(d, keys, value):
    """
    安全地在嵌套字典中设置值
    
    Args:
        d (dict): 要设置的字典
        keys (list[str], str): 键路径
        value: 要设置的值
    """
    # 性能：150 * 深度 (纳秒)
    if type(keys) is str:
        keys = keys.split('.')

    first = True
    exist = True
    prev_d = None
    prev_k = None
    prev_k2 = None
    try:
        for k in keys:
            if first:
                prev_d = d
                prev_k = k
                first = False
                continue
            try:
                # 性能比较：if key in dict: dict[key] > dict.get > dict.setdefault > try dict[key] except
                if exist and prev_k in d:
                    prev_d = d
                    d = d[prev_k]
                else:
                    exist = False
                    new = {}
                    d[prev_k] = new
                    d = new
            except TypeError:  # d不是字典
                exist = False
                d = {}
                prev_d[prev_k2] = {prev_k: d}

            prev_k2 = prev_k
            prev_k = k
    except TypeError:  # 输入keys不可迭代
        return

    # 设置最后一个键的值
    try:
        d[prev_k] = value
        return
    except TypeError:  # 最后的d不是字典
        prev_d[prev_k2] = {prev_k: value}
        return


def deep_default(d, keys, value):
    """
    安全地在嵌套字典中设置默认值
    
    Args:
        d (dict): 要设置的字典
        keys (list[str], str): 键路径
        value: 要设置的默认值
    """
    # 性能：150 * 深度 (纳秒)
    if type(keys) is str:
        keys = keys.split('.')

    first = True
    exist = True
    prev_d = None
    prev_k = None
    prev_k2 = None
    try:
        for k in keys:
            if first:
                prev_d = d
                prev_k = k
                first = False
                continue
            try:
                if exist and prev_k in d:
                    prev_d = d
                    d = d[prev_k]
                else:
                    exist = False
                    new = {}
                    d[prev_k] = new
                    d = new
            except TypeError:  # d不是字典
                exist = False
                d = {}
                prev_d[prev_k2] = {prev_k: d}

            prev_k2 = prev_k
            prev_k = k
    except TypeError:  # 输入keys不可迭代
        return

    # 设置最后一个键的默认值
    try:
        d.setdefault(prev_k, value)
        return
    except AttributeError:  # 最后的d不是字典
        prev_d[prev_k2] = {prev_k: value}
        return


def deep_pop(d, keys, default=None):
    """
    从嵌套字典和列表中弹出值
    
    Args:
        d (dict): 要操作的字典
        keys (list[str], str): 键路径
        default: 当键不存在时返回的默认值

    Returns:
        弹出的值，如果键不存在则返回默认值
    """
    if type(keys) is str:
        keys = keys.split('.')

    try:
        for k in keys[:-1]:
            d = d[k]
        return d.pop(keys[-1])
    except KeyError:  # 键不存在
        return default
    except TypeError:  # 输入keys不可迭代或d不是字典
        return default
    except IndexError:  # 输入keys超出索引
        return default
    except AttributeError:  # 最后的d不是字典
        return default


def deep_iter_depth1(data):
    """
    相当于data.items()，但如果data不是字典则抑制错误
    
    Args:
        data: 要迭代的数据

    Yields:
        Any: 键
        Any: 值
    """
    try:
        for k, v in data.items():
            yield k, v
        return
    except AttributeError:  # data不是字典
        return


def deep_iter_depth2(data):
    """
    迭代深度为2的嵌套字典中的键和值
    这是deep_iter的简化版本
    
    Args:
        data: 要迭代的数据

    Yields:
        Any: 第一层键
        Any: 第二层键
        Any: 值
    """
    try:
        for k1, v1 in data.items():
            if type(v1) is dict:
                for k2, v2 in v1.items():
                    yield k1, k2, v2
    except AttributeError:  # data不是字典
        return


def deep_iter(data, min_depth=None, depth=3):
    """
    迭代嵌套字典中的键和值
    在alas.json上（530+行，深度=3）的性能约为300微秒
    只能迭代字典类型
    
    Args:
        data: 要迭代的数据
        min_depth: 最小迭代深度
        depth: 最大迭代深度

    Yields:
        list[str]: 键路径
        Any: 值
    """
    if min_depth is None:
        min_depth = depth
    assert 1 <= min_depth <= depth

    try:
        if depth == 1:  # 相当于dict.items()
            for k, v in data.items():
                yield [k], v
            return
        elif min_depth == 1:  # 迭代第一层
            q = deque()
            for k, v in data.items():
                key = [k]
                if type(v) is dict:
                    q.append((key, v))
                else:
                    yield key, v
        else:  # 只迭代目标深度
            q = deque()
            for k, v in data.items():
                key = [k]
                if type(v) is dict:
                    q.append((key, v))
    except AttributeError:  # data不是字典
        return

    # 迭代各层
    current = 2
    while current <= depth:
        new_q = deque()
        if current == depth:  # 最大深度
            for key, data in q:
                for k, v in data.items():
                    yield key + [k], v
        elif min_depth <= current < depth:  # 在目标深度范围内
            for key, data in q:
                for k, v in data.items():
                    subkey = key + [k]
                    if type(v) is dict:
                        new_q.append((subkey, v))
                    else:
                        yield subkey, v
        else:  # 还未达到最小深度
            for key, data in q:
                for k, v in data.items():
                    subkey = key + [k]
                    if type(v) is dict:
                        new_q.append((subkey, v))
        q = new_q
        current += 1


def deep_values(data, min_depth=None, depth=3):
    """
    迭代嵌套字典中的值
    在alas.json上（530+行，深度=3）的性能约为300微秒
    只能迭代字典类型
    
    Args:
        data: 要迭代的数据
        min_depth: 最小迭代深度
        depth: 最大迭代深度

    Yields:
        Any: 值
    """
    if min_depth is None:
        min_depth = depth
    assert 1 <= min_depth <= depth

    try:
        if depth == 1:  # 相当于dict.values()
            for v in data.values():
                yield v
            return
        elif min_depth == 1:  # 迭代第一层
            q = deque()
            for v in data.values():
                if type(v) is dict:
                    q.append(v)
                else:
                    yield v
        else:  # 只迭代目标深度
            q = deque()
            for v in data.values():
                if type(v) is dict:
                    q.append(v)
    except AttributeError:  # data不是字典
        return

    # 迭代各层
    current = 2
    while current <= depth:
        new_q = deque()
        if current == depth:  # 最大深度
            for data in q:
                for v in data.values():
                    yield v
        elif min_depth <= current < depth:  # 在目标深度范围内
            for data in q:
                for v in data.values():
                    if type(v) is dict:
                        new_q.append(v)
                    else:
                        yield v
        else:  # 还未达到最小深度
            for data in q:
                for v in data.values():
                    if type(v) is dict:
                        new_q.append(v)
        q = new_q
        current += 1


def deep_iter_diff(before, after):
    """
    迭代两个字典之间的差异
    比较两个深层嵌套字典的性能很好，
    时间成本随差异数量增加而增加
    
    Args:
        before: 原始字典
        after: 新字典

    Yields:
        list[str]: 键路径
        Any: before中的值，如果不存在则为None
        Any: after中的值，如果不存在则为None
    """
    if before == after:
        return
    if type(before) is not dict or type(after) is not dict:
        yield [], before, after
        return

    queue = deque([([], before, after)])
    while True:
        new_queue = deque()
        for path, d1, d2 in queue:
            keys1 = set(d1.keys())
            keys2 = set(d2.keys())
            for key in keys1.union(keys2):
                try:
                    val2 = d2[key]
                except KeyError:
                    # 安全访问d1[key]，因为key来自两个集合的并集
                    # 如果不在d2中，那么一定在d1中
                    yield path + [key], d1[key], None
                    continue
                try:
                    val1 = d1[key]
                except KeyError:
                    yield path + [key], None, val2
                    continue
                # 首先比较字典，这很快
                if val1 != val2:
                    if type(val1) is dict and type(val2) is dict:
                        new_queue.append((path + [key], val1, val2))
                    else:
                        yield path + [key], val1, val2
        queue = new_queue
        if not queue:
            break


def deep_iter_patch(before, after):
    """
    迭代从before到after的补丁事件，类似于创建json-patch
    比较两个深层嵌套字典的性能很好，
    时间成本随差异数量增加而增加
    
    Args:
        before: 原始字典
        after: 新字典

    Yields:
        str: 操作类型（OP_ADD, OP_SET, OP_DEL）
        list[str]: 键路径
        Any: after中的值，如果是OP_DEL事件则为None
    """
    if before == after:
        return
    if type(before) is not dict or type(after) is not dict:
        yield OP_SET, [], after
        return

    queue = deque([([], before, after)])
    while True:
        new_queue = deque()
        for path, d1, d2 in queue:
            keys1 = set(d1.keys())
            keys2 = set(d2.keys())
            for key in keys1.union(keys2):
                try:
                    val2 = d2[key]
                except KeyError:
                    yield OP_DEL, path + [key], None
                    continue
                try:
                    val1 = d1[key]
                except KeyError:
                    yield OP_ADD, path + [key], val2
                    continue
                # 首先比较字典，这很快
                if val1 != val2:
                    if type(val1) is dict and type(val2) is dict:
                        new_queue.append((path + [key], val1, val2))
                    else:
                        yield OP_SET, path + [key], val2
        queue = new_queue
        if not queue:
            break
