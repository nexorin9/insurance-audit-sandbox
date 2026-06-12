"""
规则集 CRUD 路由
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models import (
    RuleDiffResult,
    RuleSetExportResult,
    RuleSetImportRequest,
    RuleSetImportResult,
    RuleSetInfo,
    RuleVersionInfo,
    ValidationResult,
)
from engine_rules.version_manager import (
    compare_rule_set_versions,
    export_rule_set,
    get_rule_set_versions,
    import_rule_set,
    init_rules_git_repo,
)

logger = logging.getLogger("api.routes.rules")

# ---- 规则集目录 ----
RULES_DIR = Path(__file__).parent.parent.parent / "engine" / "rules"
RULES_INDEX_FILE = RULES_DIR / "rules_index.yaml"


class ValidateRequest(BaseModel):
    yaml_content: str


def _load_rules_index() -> list[dict[str, Any]]:
    """加载规则集索引文件"""
    if not RULES_INDEX_FILE.exists():
        return []
    with open(RULES_INDEX_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rule_sets_index", [])


def _build_rule_set_id(name: str) -> str:
    """从 YAML 文件名构建 rule_set_id"""
    return name.replace(".yaml", "")


def _list_rule_yaml_files() -> list[Path]:
    """列出 rules/ 下所有 .yaml 文件（排除 index）"""
    if not RULES_DIR.exists():
        return []
    return [f for f in RULES_DIR.glob("*.yaml") if f.name != "rules_index.yaml"]


router = APIRouter(prefix="/rules", tags=["规则集"])


@router.get("", response_model=list[RuleSetInfo])
async def list_rule_sets():
    """列出系统中所有已注册的规则集。

    优先从 rules_index.yaml 读取元数据；若索引不存在则扫描 rules/ 目录下所有 YAML 文件。

    Returns:
        list[RuleSetInfo]: 规则集信息列表，按 rule_set_id 升序排列。
    """
    index = _load_rules_index()
    if index:
        return [
            RuleSetInfo(
                rule_set_id=item["rule_set_id"],
                name=item["name"],
                version=item["version"],
                rule_count=item["rule_count"],
                description=item.get("description"),
                updated_at=item.get("updated_at"),
            )
            for item in index
        ]

    # fallback: 扫描 YAML 文件
    files = _list_rule_yaml_files()
    result: list[RuleSetInfo] = []
    for f in files:
        rule_set_id = _build_rule_set_id(f.name)
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            rules = data.get("rules", [])
            result.append(
                RuleSetInfo(
                    rule_set_id=rule_set_id,
                    name=data.get("name", rule_set_id),
                    version=data.get("version", "1.0.0"),
                    rule_count=len(rules),
                    description=data.get("description"),
                    updated_at=data.get("updated_at"),
                )
            )
        except Exception as e:
            logger.warning("加载规则集 %s 失败: %s", rule_set_id, e)
            result.append(
                RuleSetInfo(
                    rule_set_id=rule_set_id,
                    name=rule_set_id,
                    version="unknown",
                    rule_count=0,
                    description=None,
                    updated_at=None,
                )
            )
    return result


@router.post("/validate", response_model=ValidationResult)
async def validate_rule_yaml(body: ValidateRequest):
    """验证规则 YAML 内容的格式与必填字段。

    检查项：根对象类型、必填字段（rule_set_id/name/version/rules）、
    rule_id 唯一性、risk_score 范围（0~100）。

    Args:
        body: 包含 yaml_content 字段的请求体。

    Returns:
        ValidationResult: valid=true 表示校验通过；errors 列表说明具体错误。
    """
    yaml_content = body.yaml_content
    if not yaml_content.strip():
        return ValidationResult(valid=False, errors=["YAML 内容为空"], rule_count=0)

    errors: list[str] = []
    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            errors.append("根对象必须是字典")
            return ValidationResult(valid=False, errors=errors, rule_count=0)

        # 必填字段检查
        for field in ("rule_set_id", "name", "version", "rules"):
            if field not in data:
                errors.append(f"缺少必填字段: {field}")

        rules = data.get("rules", [])
        if not isinstance(rules, list):
            errors.append("rules 必须是列表")
        else:
            rule_ids: set[str] = set()
            for i, rule in enumerate(rules, 1):
                if not isinstance(rule, dict):
                    errors.append(f"规则 #{i} 必须是字典")
                    continue
                for f in ("rule_id", "name", "condition", "risk_score", "category"):
                    if f not in rule:
                        errors.append(f"规则 #{i} 缺少字段: {f}")
                if "rule_id" in rule:
                    rid = rule["rule_id"]
                    if rid in rule_ids:
                        errors.append(f"规则 ID 重复: {rid}")
                    rule_ids.add(rid)
                # risk_score 范围检查
                rs = rule.get("risk_score")
                if rs is not None and not (0 <= rs <= 100):
                    errors.append(f"规则 #{i} risk_score 须在 0-100 之间")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            rule_count=len(rules) if isinstance(rules, list) else 0,
        )
    except yaml.YAMLError as e:
        return ValidationResult(valid=False, errors=[f"YAML 解析错误: {e}"], rule_count=0)


@router.get("/{rule_set_id}")
async def get_rule_set(rule_set_id: str):
    """获取指定规则集的完整详情，包括所有规则条目。

    优先从 rules_index.yaml 定位；若未找到则直接加载对应 YAML 文件。

    Args:
        rule_set_id: 规则集唯一标识（对应 YAML 文件名，不含 .yaml 后缀）。

    Returns:
        包含 rule_set_id/name/version/description/rules 的完整规则集对象。

    Raises:
        404: 规则集文件不存在。
    """
    # 优先从 index 查找
    index = _load_rules_index()
    for item in index:
        if item["rule_set_id"] == rule_set_id:
            yaml_file = RULES_DIR / f"{rule_set_id}.yaml"
            if not yaml_file.exists():
                raise HTTPException(status_code=404, detail=f"规则集文件 {rule_set_id}.yaml 不存在")
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return {
                **item,
                "rules": data.get("rules", []),
            }

    # fallback: 直接加载文件
    yaml_file = RULES_DIR / f"{rule_set_id}.yaml"
    if not yaml_file.exists():
        raise HTTPException(status_code=404, detail=f"规则集 {rule_set_id} 不存在")
    with open(yaml_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    rules = data.get("rules", [])
    return {
        "rule_set_id": data.get("rule_set_id", rule_set_id),
        "name": data.get("name", rule_set_id),
        "version": data.get("version", "1.0.0"),
        "description": data.get("description"),
        "updated_at": data.get("updated_at"),
        "rule_count": len(rules),
        "rules": rules,
    }


@router.get("/{rule_set_id}/versions", response_model=list[RuleVersionInfo])
async def get_rule_set_version_history(rule_set_id: str):
    """获取指定规则集的 Git 版本历史（最近 N 次提交）。

    rules/ 目录须已初始化为 Git 仓库（由 init_rules_git_repo 自动处理）。

    Args:
        rule_set_id: 规则集唯一标识。

    Returns:
        list[RuleVersionInfo]: 按提交时间倒序的版本历史列表。

    Raises:
        404: 规则集无版本历史（尚未提交）。
    """
    init_result = init_rules_git_repo()
    versions = get_rule_set_versions(rule_set_id)
    if not versions:
        raise HTTPException(status_code=404, detail=f"规则集 {rule_set_id} 无版本历史")
    return versions


@router.get("/{rule_set_id}/diff", response_model=RuleDiffResult)
async def diff_rule_set(rule_set_id: str, compare_version: str):
    """对比规则集当前版本与指定历史版本的差异。

    通过 Git diff 实现，返回新增、删除、修改的规则列表及统计摘要。

    Args:
        rule_set_id: 规则集唯一标识。
        compare_version: 要对比的历史版本 commit hash（前 8 位即可）。

    Returns:
        RuleDiffResult: 包含 diff 文本、差异摘要及具体规则列表。

    Raises:
        404: 指定版本不存在或规则集无 Git 历史。
    """
    init_result = init_rules_git_repo()
    try:
        result = compare_rule_set_versions(rule_set_id, compare_version)
        return RuleDiffResult(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/import", response_model=RuleSetImportResult)
async def import_rule_set_endpoint(body: RuleSetImportRequest):
    """将 YAML 规则集内容导入到 rules/ 目录。

    导入前自动校验格式（与 POST /rules/validate 等价）；
    导入后自动 commit 到 Git 仓库。

    Args:
        body: 包含 rule_set_id 和完整 yaml_content 的请求体。

    Returns:
        RuleSetImportResult: status=success 表示导入并提交成功。

    Raises:
        400: YAML 格式错误或 rule_set_id 冲突。
    """
    init_result = init_rules_git_repo()
    result = import_rule_set(body.rule_set_id, body.yaml_content)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return RuleSetImportResult(**result)


@router.get("/{rule_set_id}/export", response_model=RuleSetExportResult)
async def export_rule_set_endpoint(rule_set_id: str):
    """导出指定规则集的完整 YAML 原文。

    从 rules/{rule_set_id}.yaml 读取并返回，供备份或跨环境迁移。

    Args:
        rule_set_id: 规则集唯一标识。

    Returns:
        RuleSetExportResult: 包含 rule_set_id 和 yaml_content。

    Raises:
        404: 规则集文件不存在。
    """
    try:
        content = export_rule_set(rule_set_id)
        return RuleSetExportResult(rule_set_id=rule_set_id, yaml_content=content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))