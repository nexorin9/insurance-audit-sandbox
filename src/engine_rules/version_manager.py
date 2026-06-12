"""
规则集版本管理器 — 基于 Git 实现规则集版本化管理
"""

import logging
import subprocess
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("engine.version_manager")

# 规则文件目录: src/engine/rules/
RULES_DIR = Path(__file__).parent.parent / "engine" / "rules"


def _run_git(cwd: Path, *args: str) -> tuple[int, str, str]:
    """执行 git 命令，返回 (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "git 命令不可用"


def init_rules_git_repo() -> dict[str, Any]:
    """初始化 rules/ 目录的 git 仓库"""
    if not RULES_DIR.exists():
        RULES_DIR.mkdir(parents=True, exist_ok=True)

    rc, stdout, stderr = _run_git(RULES_DIR, "status")
    if rc == 0:
        return {"status": "already_git", "message": "已是 Git 仓库"}

    rc, stdout, stderr = _run_git(RULES_DIR, "init")
    if rc != 0:
        return {"status": "error", "message": stderr}

    # 初始提交所有现有规则文件
    rc, stdout, stderr = _run_git(RULES_DIR, "add", ".")
    if rc != 0:
        logger.warning("git add 失败: %s", stderr)

    rc, stdout, stderr = _run_git(RULES_DIR, "commit", "-m", "initial: 初始规则集")
    if rc != 0:
        logger.warning("git commit 失败: %s", stderr)
        return {"status": "initialized", "message": "git init 成功，初始提交失败（可能无可提交内容）"}

    return {"status": "success", "message": "git 仓库初始化成功"}


def get_rule_set_versions(rule_set_id: str) -> list[dict[str, Any]]:
    """获取规则集的版本历史"""
    yaml_file = RULES_DIR / f"{rule_set_id}.yaml"
    if not yaml_file.exists():
        return []

    rc, stdout, stderr = _run_git(RULES_DIR, "log", "--format=%H|%cd|%s", "--", yaml_file.name)
    if rc != 0:
        return []

    versions: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            versions.append({
                "commit_hash": parts[0],
                "committed_at": parts[1],
                "message": parts[2],
            })
    return versions


def get_rule_set_file_content(rule_set_id: str, version: str = "HEAD") -> str:
    """获取规则集文件在指定版本的内容"""
    yaml_file = RULES_DIR / f"{rule_set_id}.yaml"
    rc, stdout, stderr = _run_git(RULES_DIR, "show", f"{version}:{yaml_file.name}")
    if rc != 0:
        raise ValueError(f"无法获取规则集 {rule_set_id} 版本 {version}: {stderr}")
    return stdout


def compare_rule_set_versions(rule_set_id: str, compare_version: str) -> dict[str, Any]:
    """对比规则集两个版本的差异"""
    yaml_file = RULES_DIR / f"{rule_set_id}.yaml"
    if not yaml_file.exists():
        raise ValueError(f"规则集文件 {rule_set_id}.yaml 不存在")

    # 获取当前版本（HEAD）和指定版本的内容
    rc_current, current_content, _ = _run_git(RULES_DIR, "show", f"HEAD:{yaml_file.name}")
    rc_compare, compare_content, stderr = _run_git(RULES_DIR, "show", f"{compare_version}:{yaml_file.name}")

    if rc_compare != 0:
        raise ValueError(f"版本 {compare_version} 不存在: {stderr}")

    # 使用 git diff 对比
    rc, diff_output, _ = _run_git(
        RULES_DIR, "diff", "--no-color",
        f"{compare_version}:{yaml_file.name}", f"HEAD:{yaml_file.name}",
        "--", yaml_file.name
    )

    # 解析两个版本的规则列表
    current_data = yaml.safe_load(current_content) or {}
    compare_data = yaml.safe_load(compare_content) or {}

    current_rules = current_data.get("rules", [])
    compare_rules = compare_data.get("rules", [])

    current_rule_ids = {r["rule_id"] for r in current_rules if "rule_id" in r}
    compare_rule_ids = {r["rule_id"] for r in compare_rules if "rule_id" in r}

    added = [r for r in current_rules if r.get("rule_id") in (current_rule_ids - compare_rule_ids)]
    removed = [r for r in compare_rules if r.get("rule_id") in (compare_rule_ids - current_rule_ids)]
    common_ids = current_rule_ids & compare_rule_ids

    modified = []
    for r in current_rules:
        if r.get("rule_id") in common_ids:
            old = next((o for o in compare_rules if o["rule_id"] == r["rule_id"]), None)
            if old and old != r:
                modified.append({"new": r, "old": old})

    return {
        "rule_set_id": rule_set_id,
        "compare_version": compare_version,
        "current_version": "HEAD",
        "diff": diff_output if rc == 0 else "",
        "summary": {
            "rules_added": len(added),
            "rules_removed": len(removed),
            "rules_modified": len(modified),
        },
        "added_rules": added,
        "removed_rules": removed,
        "modified_rules": modified,
    }


def import_rule_set(rule_set_id: str, yaml_content: str) -> dict[str, Any]:
    """导入规则集 YAML 内容到 rules/ 目录"""
    # 验证 YAML 格式
    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            return {"status": "error", "message": "YAML 内容必须是字典对象"}
        if "rules" not in data:
            return {"status": "error", "message": "缺少 rules 字段"}
    except yaml.YAMLError as e:
        return {"status": "error", "message": f"YAML 解析错误: {e}"}

    yaml_file = RULES_DIR / f"{rule_set_id}.yaml"
    # 备份旧版本（如果存在）
    old_content = ""
    if yaml_file.exists():
        old_content = yaml_file.read_text(encoding="utf-8")

    # 写入新版本
    yaml_file.write_text(yaml_content, encoding="utf-8")

    # git add + commit
    rc, _, stderr = _run_git(RULES_DIR, "add", yaml_file.name)
    if rc != 0:
        logger.warning("git add 失败: %s", stderr)

    rc, _, stderr = _run_git(RULES_DIR, "commit", "-m", f"import: 更新规则集 {rule_set_id}")
    if rc != 0:
        logger.warning("git commit 失败: %s（可能内容未变）", stderr)
        # 如果内容未变，尝试恢复旧版本
        if old_content:
            yaml_file.write_text(old_content, encoding="utf-8")
        return {"status": "error", "message": f"提交失败: {stderr}"}

    return {"status": "success", "message": f"规则集 {rule_set_id} 导入成功"}


def export_rule_set(rule_set_id: str) -> str:
    """导出租房集 YAML 内容"""
    yaml_file = RULES_DIR / f"{rule_set_id}.yaml"
    if not yaml_file.exists():
        raise ValueError(f"规则集文件 {rule_set_id}.yaml 不存在")
    return yaml_file.read_text(encoding="utf-8")