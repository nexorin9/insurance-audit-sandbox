"""
规则引擎 — 条件操作符库
定义所有支持的条件操作符，供规则执行器调用。
"""

import re
import logging
from typing import Any, Union

logger = logging.getLogger(__name__)

Number = Union[int, float]


def eq(a: Any, b: Any) -> bool:
    """相等比较"""
    try:
        return _to_num(a) == _to_num(b) if (_is_num(a) or _is_num(b)) else a == b
    except Exception:
        return False


def neq(a: Any, b: Any) -> bool:
    """不相等比较"""
    try:
        return _to_num(a) != _to_num(b) if (_is_num(a) or _is_num(b)) else a != b
    except Exception:
        return False


def gt(a: Any, b: Any) -> bool:
    """大于比较"""
    try:
        return _to_num(a) > _to_num(b)
    except Exception:
        logger.warning("gt: type mismatch for %s > %s", a, b)
        return False


def gte(a: Any, b: Any) -> bool:
    """大于等于比较"""
    try:
        return _to_num(a) >= _to_num(b)
    except Exception:
        logger.warning("gte: type mismatch for %s >= %s", a, b)
        return False


def lt(a: Any, b: Any) -> bool:
    """小于比较"""
    try:
        return _to_num(a) < _to_num(b)
    except Exception:
        logger.warning("lt: type mismatch for %s < %s", a, b)
        return False


def lte(a: Any, b: Any) -> bool:
    """小于等于比较"""
    try:
        return _to_num(a) <= _to_num(b)
    except Exception:
        logger.warning("lte: type mismatch for %s <= %s", a, b)
        return False


def in_(val: Any, target_list: list) -> bool:
    """成员检查：val in [list]"""
    try:
        if not isinstance(target_list, (list, tuple)):
            logger.warning("in_: target_list must be list/tuple, got %s", type(target_list).__name__)
            return False
        return val in target_list
    except Exception:
        logger.warning("in_: error checking %s in %s", val, target_list)
        return False


def between(val: Any, lo: Any, hi: Any) -> bool:
    """区间检查：lo <= val <= hi"""
    try:
        v = _to_num(val)
        return _to_num(lo) <= v <= _to_num(hi)
    except Exception:
        logger.warning("between: type mismatch for %s <= %s <= %s", lo, val, hi)
        return False


def contains(haystack: Any, needle: Any) -> bool:
    """字符串/列表包含检查"""
    try:
        if haystack is None:
            return False
        if isinstance(haystack, (list, tuple)):
            return needle in haystack
        if isinstance(haystack, str):
            return str(needle) in haystack
        return False
    except Exception:
        logger.warning("contains: error checking %s in %s", needle, haystack)
        return False


def regex(pattern: str, text: Any) -> bool:
    """正则表达式匹配"""
    try:
        if text is None:
            return False
        return bool(re.search(pattern, str(text)))
    except re.error as e:
        logger.warning("regex: invalid pattern %s: %s", pattern, e)
        return False
    except Exception as e:
        logger.warning("regex: error matching %s against %s: %s", pattern, text, e)
        return False


# ---- 操作符注册表 ----
OPERATORS = {
    "eq": eq,
    "neq": neq,
    "gt": gt,
    "gte": gte,
    "lt": lt,
    "lte": lte,
    "in": in_,
    "between": between,
    "contains": contains,
    "regex": regex,
}


def apply_op(op: str, field_value: Any, *args) -> bool:
    """
    根据操作符名称调用对应函数。

    Args:
        op: 操作符名称（如 eq, gt, in, between）
        field_value: 字段值
        *args: 操作符参数（in/between/contains/regex 需要额外参数）

    Returns:
        布尔比较结果
    """
    if op not in OPERATORS:
        logger.warning("apply_op: unknown operator %s", op)
        return False

    fn = OPERATORS[op]
    try:
        if op in ("in",):
            # in 需要 (field_value, list)
            return fn(field_value, *args)
        elif op in ("between",):
            # between 需要 (field_value, lo, hi)
            return fn(field_value, *args)
        elif op in ("contains",):
            # contains 需要 (haystack, needle)
            return fn(field_value, *args)
        elif op in ("regex",):
            # regex 需要 (pattern, text)
            return fn(field_value, *args)
        else:
            # eq/neq/gt/gte/lt/lte: (a, b)
            return fn(field_value, *args)
    except Exception as e:
        logger.warning("apply_op(%s, %s, %s) failed: %s", op, field_value, args, e)
        return False


# ---- 辅助函数 ----
def _is_num(v) -> bool:
    return isinstance(v, (int, float))


def _to_num(v) -> Number:
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ValueError(f"cannot convert {v!r} to number")
