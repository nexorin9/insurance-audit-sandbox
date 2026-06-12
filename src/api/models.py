"""
API 数据模型 — Pydantic 定义
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FeeItem(BaseModel):
    """费用明细输入模型 — 供演练执行接口接收费用数据"""
    item_id: str = Field(..., description="费用唯一标识（UUID 或业务编码）")
    category: str = Field(
        ...,
        description="费用类别",
        examples=["药品", "耗材", "手术", "检查", "床位"],
    )
    amount: float = Field(..., description="费用总额（元）", ge=0)
    unit_price: Optional[float] = Field(None, description="单价（元）", ge=0)
    quantity: Optional[int] = Field(None, description="数量", ge=1)
    material_markup_rate: Optional[float] = Field(
        None, description="耗材加价率（耗材类费用填写，范围 0~1）", ge=0, le=1
    )
    injection_type: Optional[str] = Field(
        None,
        description="注射剂类型（药品类费用填写，如：中药注射剂、西药注射剂）",
        examples=["中药注射剂", "西药注射剂"],
    )
    days_admitted: Optional[int] = Field(None, description="住院天数（住院费用填写）", ge=1)
    procedure_code: Optional[str] = Field(None, description="手术操作代码（手术类费用填写）")

    class Config:
        json_schema_extra = {
            "example": {
                "item_id": "FI-20260613-001",
                "category": "药品",
                "amount": 1580.00,
                "unit_price": 158.00,
                "quantity": 10,
                "material_markup_rate": None,
                "injection_type": "中药注射剂",
                "days_admitted": None,
                "procedure_code": None,
            }
        }


class HitResult(BaseModel):
    """规则命中结果模型 — 记录单条费用明细被规则命中的详情"""
    item_id: str = Field(..., description="被命中的费用ID")
    rule_id: str = Field(..., description="命中规则的唯一标识")
    name: str = Field(..., description="命中规则的中文名称")
    category: str = Field(..., description="规则所属业务类别")
    risk_score: float = Field(..., description="该规则的风险评分（0~100）", ge=0, le=100)
    amount: Optional[float] = Field(None, description="费用金额（元）")
    matched_condition: str = Field(..., description="触发该命中的具体条件表达式")

    class Config:
        json_schema_extra = {
            "example": {
                "item_id": "FI-20260613-001",
                "rule_id": "R-001",
                "name": "中药注射剂超限",
                "category": "药品",
                "risk_score": 75.0,
                "amount": 1580.00,
                "matched_condition": "injection_type in [中药注射剂] AND amount > 1000",
            }
        }


class RiskDistributionItem(BaseModel):
    """风险分布单项 — 按费用类别统计的命中次数与平均风险分"""
    count: int = Field(..., description="该类别费用明细命中规则的次数", ge=0)
    avg_score: float = Field(..., description="该类别费用明细的平均风险评分（0~100）", ge=0, le=100)


class SandboxRun(BaseModel):
    """演练执行结果模型 — 完整演练记录（含统计摘要）"""
    run_id: str = Field(..., description="演练记录唯一ID（UUID）")
    timestamp: str = Field(..., description="演练执行时间（ISO 8601 格式）")
    rule_set_version: str = Field(..., description="执行时使用的规则集版本号")
    total_items: int = Field(..., description="本次演练输入的费用明细总条数", ge=0)
    hit_count: int = Field(..., description="被至少一条规则命中的费用明细条数", ge=0)
    hit_rate: float = Field(..., description="命中率（hit_count / total_items）", ge=0, le=1)
    overall_risk_score: float = Field(..., description="整体风险评分（0~100）", ge=0, le=100)
    risk_distribution: dict[str, RiskDistributionItem] = Field(
        default_factory=dict,
        description="风险分布，按费用类别统计命中次数与平均风险分",
    )
    top_risk_categories: list[dict[str, Any]] = Field(
        default_factory=list,
        description="TOP 高风险类别列表，按平均风险分降序",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2026-06-13T03:21:00Z",
                "rule_set_version": "0.1.0",
                "total_items": 50,
                "hit_count": 8,
                "hit_rate": 0.16,
                "overall_risk_score": 72.5,
                "risk_distribution": {
                    "药品": {"count": 5, "avg_score": 78.0}
                },
                "top_risk_categories": [
                    {
                        "category": "药品",
                        "avg_score": 78.0,
                        "hit_count": 5,
                        "total_amount": 7900.00,
                    }
                ],
            }
        }


class SandboxRunCreate(BaseModel):
    """创建演练请求模型 — POST /sandbox/run 的请求体"""
    rule_set_id: str = Field(
        ...,
        description="执行演练所使用的规则集ID（如 zhongyao_injection_limit）",
        examples=["zhongyao_injection_limit"],
    )
    fee_items: list[FeeItem] = Field(
        ...,
        description="费用明细列表，支持 1~10000 条",
        min_length=1,
    )


class RuleSetInfo(BaseModel):
    """规则集信息模型 — 规则集的元数据摘要"""
    rule_set_id: str = Field(..., description="规则集唯一标识（对应 YAML 文件名）")
    name: str = Field(..., description="规则集中文名称")
    version: str = Field(..., description="规则集语义化版本号", examples=["1.0.0"])
    rule_count: int = Field(..., description="规则集中包含的规则条数", ge=0)
    description: Optional[str] = Field(None, description="规则集用途描述")
    updated_at: Optional[str] = Field(None, description="规则集最后更新时间（ISO 8601）")


class HealthResponse(BaseModel):
    """健康检查响应 — 验证 API 服务是否正常运行"""
    status: str = Field(..., description="服务状态（ok=正常）", examples=["ok"])
    timestamp: str = Field(..., description="服务器当前时间（ISO 8601）")


class ReadyResponse(BaseModel):
    """就绪检查响应 — 验证 API 服务是否已完成初始化"""
    status: str = Field(..., description="就绪状态（ready=已就绪）", examples=["ready"])
    rules_loaded: int = Field(..., description="服务启动时扫描到的规则集数量", ge=0)


class ValidationResult(BaseModel):
    """规则验证结果 — POST /rules/validate 的响应"""
    valid: bool = Field(..., description="YAML 内容是否通过格式与字段校验")
    errors: list[str] = Field(
        default_factory=list,
        description="校验失败时的错误信息列表（为空表示校验通过）",
    )
    rule_count: int = Field(default=0, description="解析出的规则条数（校验失败时为 0）", ge=0)


class RuleVersionInfo(BaseModel):
    """规则集版本历史条目 — Git commit 记录"""
    commit_hash: str = Field(..., description="Git commit SHA（前 8 位）")
    committed_at: str = Field(..., description="提交时间（ISO 8601）")
    message: str = Field(..., description="Git commit 提交信息")


class RuleDiffSummary(BaseModel):
    """规则差异摘要 — 两版本规则集的增删改统计"""
    rules_added: int = Field(..., description="新增规则条数", ge=0)
    rules_removed: int = Field(..., description="删除规则条数", ge=0)
    rules_modified: int = Field(..., description="修改规则条数", ge=0)


class RuleDiffResult(BaseModel):
    """规则集版本对比结果 — GET /rules/{rule_set_id}/diff 的响应"""
    rule_set_id: str = Field(..., description="规则集ID")
    compare_version: str = Field(..., description="被比较的历史版本 commit hash")
    current_version: str = Field(..., description="当前版本 commit hash")
    diff: str = Field(default="", description="Git diff 完整输出")
    summary: RuleDiffSummary = Field(..., description="差异统计摘要")
    added_rules: list[dict[str, Any]] = Field(default_factory=list, description="新增的规则列表")
    removed_rules: list[dict[str, Any]] = Field(default_factory=list, description="删除的规则列表")
    modified_rules: list[dict[str, Any]] = Field(default_factory=list, description="修改的规则列表")


class RuleSetImportRequest(BaseModel):
    """规则集导入请求 — POST /rules/import 的请求体"""
    rule_set_id: str = Field(
        ...,
        description="导入规则集的ID（将作为 YAML 文件名）",
        examples=["custom_rule_set_001"],
    )
    yaml_content: str = Field(..., description="规则集完整 YAML 内容")


class RuleSetImportResult(BaseModel):
    """规则集导入结果 — POST /rules/import 的响应"""
    status: str = Field(..., description="导入结果状态（success=成功，error=失败）")
    message: str = Field(..., description="结果描述或错误原因")


class RuleSetExportResult(BaseModel):
    """规则集导出结果 — GET /rules/{rule_set_id}/export 的响应"""
    rule_set_id: str = Field(..., description="规则集ID")
    yaml_content: str = Field(..., description="规则集完整 YAML 原文")