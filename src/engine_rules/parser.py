"""
规则引擎 — YAML 规则解析器
解析规则集 YAML 文件，验证格式，输出结构化规则对象列表。
"""

import yaml
import re
from pathlib import Path
from typing import Any


class RuleValidationError(Exception):
    """规则格式验证错误"""
    pass


def parse_rule_yaml(yaml_path: str | Path) -> list[dict]:
    """
    解析 YAML 规则集文件。

    Args:
        yaml_path: YAML 文件路径

    Returns:
        结构化规则对象列表，每个对象包含：
        rule_id, name, condition, risk_score, category

    Raises:
        RuleValidationError: 格式错误时抛出
    """
    path = Path(yaml_path)
    if not path.exists():
        raise RuleValidationError(f"规则文件不存在: {yaml_path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise RuleValidationError(f"规则文件为空: {yaml_path}")

    # 提取规则列表（支持三种格式）
    if isinstance(raw, dict) and "rules" in raw:
        # 格式: {rules: [...]} — 规则集索引包装
        rules = raw["rules"]
    elif isinstance(raw, dict) and "rule_id" in raw:
        # 格式: {rule_id, name, ...} — 单条规则
        rules = [raw]
    elif isinstance(raw, list):
        # 格式: [...] — 直接规则列表
        rules = raw
    else:
        raise RuleValidationError(
            f"规则文件格式无效：期望 {{rules:[...]}} / {{rule_id,...}} / [...]，"
            f"得到 {type(raw).__name__}"
        )

    if not isinstance(rules, list):
        raise RuleValidationError(f"规则须为列表，得到 {type(rules).__name__}")

    seen_ids: set[str] = set()
    parsed: list[dict] = []

    for idx, rule in enumerate(rules):
        _validate_single_rule(rule, idx, seen_ids, parsed)

    return parsed


def _validate_single_rule(
    rule: Any, idx: int, seen_ids: set[str], parsed: list[dict]
) -> None:
    """验证并解析单条规则"""
    if not isinstance(rule, dict):
        raise RuleValidationError(f"规则 #{idx + 1} 须为字典，得到 {type(rule).__name__}")

    rule_id = rule.get("rule_id")
    if not rule_id or not isinstance(rule_id, str):
        raise RuleValidationError(f"规则 #{idx + 1} 缺少或无效 rule_id")

    if rule_id in seen_ids:
        raise RuleValidationError(f"规则 #{idx + 1} 的 rule_id='{rule_id}' 重复")

    name = rule.get("name")
    if not name or not isinstance(name, str):
        raise RuleValidationError(f"规则 #{idx + 1} 缺少或无效 name")

    condition = rule.get("condition")
    if not condition or not isinstance(condition, (str, dict)):
        raise RuleValidationError(
            f"规则 #{idx + 1} (rule_id={rule_id}) 的 condition 缺失或类型无效"
        )

    risk_score = rule.get("risk_score")
    _validate_risk_score(risk_score, idx, rule_id)

    category = rule.get("category")
    if not category or not isinstance(category, str):
        raise RuleValidationError(
            f"规则 #{idx + 1} (rule_id={rule_id}) 缺少或无效 category"
        )

    seen_ids.add(rule_id)

    parsed.append({
        "rule_id": rule_id,
        "name": name,
        "condition": condition,
        "risk_score": risk_score,
        "category": category,
    })


def _validate_risk_score(score: Any, idx: int, rule_id: str) -> None:
    if score is None:
        raise RuleValidationError(f"规则 #{idx + 1} (rule_id={rule_id}) 缺少 risk_score")
    if not isinstance(score, (int, float)):
        raise RuleValidationError(
            f"规则 #{idx + 1} (rule_id={rule_id}) risk_score 须为数值，得到 {type(score).__name__}"
        )
    if not (0 <= score <= 100):
        raise RuleValidationError(
            f"规则 #{idx + 1} (rule_id={rule_id}) risk_score={score} 超出范围 [0, 100]"
        )


def parse_condition_expr(condition: str | dict) -> dict:
    """
    解析条件表达式。

    支持两种格式：
    - 简写字符串: "amount > 1000"
    - 结构化 dict: {"op": "gt", "field": "amount", "value": 1000}

    Returns:
        标准化条件对象 {"op", "field", "value"}
    """
    if isinstance(condition, dict):
        if "op" not in condition or "field" not in condition:
            raise RuleValidationError(
                f"结构化 condition 须包含 op 和 field 字段，得到 {condition}"
            )
        return dict(condition)

    if isinstance(condition, str):
        # 解析简单表达式: "amount > 1000" / "category in [药品, 耗材]"
        condition = condition.strip()
        # 匹配操作符
        m = re.match(r"(.+?)\s*(>=|<=|!=|==|>|<|in|between)\s*(.+)", condition)
        if not m:
            raise RuleValidationError(f"无法解析条件表达式: {condition}")

        field = m.group(1).strip()
        op = m.group(2).strip()
        raw_value = m.group(3).strip()

        # 转换操作符
        op_map = {
            ">": "gt", ">=": "gte", "<": "lt", "<=": "lte",
            "==": "eq", "!=": "neq", "in": "in", "between": "between",
        }
        if op not in op_map:
            raise RuleValidationError(f"不支持的操作符: {op}")
        op = op_map[op]

        # 解析值
        value = _parse_raw_value(raw_value)

        return {"op": op, "field": field, "value": value}

    raise RuleValidationError(f"condition 类型无效: {type(condition).__name__}")


def _parse_raw_value(raw: str):
    """解析 YAML 表达式中的原始值"""
    raw = raw.strip()
    # 列表: [药品, 耗材]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        items = [s.strip().strip("'\"") for s in inner.split(",")]
        return items
    # 数字
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        pass
    # 布尔
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    # 字符串（去引号）
    if (raw.startswith("'") and raw.endswith("'")) or (
        raw.startswith('"') and raw.endswith('"')
    ):
        return raw[1:-1]
    return raw


# ---- 内置操作符注册表 ----
OPERATORS = {
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
    "gt": lambda a, b: _to_num(a) > _to_num(b) if (_is_num(a) or _is_num(b)) else a > b,
    "gte": lambda a, b: _to_num(a) >= _to_num(b) if (_is_num(a) or _is_num(b)) else a >= b,
    "lt": lambda a, b: _to_num(a) < _to_num(b) if (_is_num(a) or _is_num(b)) else a < b,
    "lte": lambda a, b: _to_num(a) <= _to_num(b) if (_is_num(a) or _is_num(b)) else a <= b,
}


def _is_num(v) -> bool:
    return isinstance(v, (int, float))


def _to_num(v):
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return v