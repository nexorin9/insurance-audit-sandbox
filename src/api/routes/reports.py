"""
报告生成路由
POST /reports/generate — 生成 PDF/Word 整改建议报告
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from report.pdf_generator import PdfReportGenerator
from report.word_generator import WordReportGenerator
from ..db import get_sandbox_run

logger = logging.getLogger("api.routes.reports")

router = APIRouter(prefix="/reports", tags=["报告"])


class ReportGenerateRequest(BaseModel):
    """报告生成请求 — POST /reports/generate 的请求体"""
    run_id: str = Field(
        ...,
        description="演练记录ID（从 POST /sandbox/run 获得）",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    format: str = Field(
        default="pdf",
        description="报告格式：pdf（默认）或 docx",
        examples=["pdf", "docx"],
    )


class ReportGenerateResponse(BaseModel):
    """报告生成响应 — 直接返回文件流（RFC 6266 Content-Disposition）"""
    run_id: str = Field(..., description="对应的演练记录ID")
    format: str = Field(..., description="生成的报告格式（pdf 或 docx）")
    file_size: int = Field(..., description="报告文件大小（字节）", ge=0)


def _fetch_run_data(run_id: str) -> dict:
    """从数据库获取演练记录数据，构造报告所需字段"""
    record = get_sandbox_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"演练记录 {run_id} 不存在")

    if record.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="该演练已被取消，无法生成报告")

    hit_items = record.get("hit_items", [])
    risk_distribution = record.get("risk_distribution", {})
    top_risk_categories = record.get("top_risk_categories", [])

    # 构造 TOP 类别（兼容已存储的 top_risk_categories）
    if not top_risk_categories and hit_items:
        from engine_rules.scorer import get_top_risk_categories
        top_risk_categories = get_top_risk_categories(hit_items, top_n=5)

    return {
        "run_id": run_id,
        "timestamp": record.get("timestamp", ""),
        "rule_set_version": record.get("rule_set_version", "0.1.0"),
        "total_items": record.get("total_items", 0),
        "hit_items": hit_items,
        "risk_distribution": risk_distribution,
        "top_risk_categories": top_risk_categories,
    }


# ---- 生成报告 ----
@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    responses={
        200: {
            "content": {
                "application/pdf": {},
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {},
            },
            "media_type": "application/octet-stream",
        }
    },
)
async def generate_report(body: ReportGenerateRequest):
    """
    生成 PDF 或 Word 整改建议报告。

    报告包含：
    - 高风险项清单（含费用ID、类别、金额、风险分、规则名称、匹配条件）
    - TOP 高风险类别汇总
    - 整改建议

    返回文件流（Content-Disposition: attachment）。
    """
    fmt = body.format.lower().strip()
    if fmt not in ("pdf", "docx"):
        raise HTTPException(
            status_code=400,
            detail="不支持的格式，仅支持 pdf 或 docx",
        )

    # 获取演练数据
    data = _fetch_run_data(body.run_id)

    # 生成报告
    if fmt == "pdf":
        generator = PdfReportGenerator()
        file_bytes = generator.generate(**data)
        media_type = "application/pdf"
        ext = "pdf"
    else:
        generator = WordReportGenerator()
        file_bytes = generator.generate(**data)
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        ext = "docx"

    filename = f"整改建议报告_{body.run_id[:8]}.{ext}"

    logger.info(
        "报告生成完成 run_id=%s format=%s size=%d",
        body.run_id, fmt, len(file_bytes),
    )

    import urllib.parse
    ascii_filename = f"report_{body.run_id[:8]}.{ext}"
    header_value = (
        f"attachment; filename={ascii_filename}; "
        f"filename*=utf-8''{urllib.parse.quote(filename, safe='')}"
    )
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": header_value,
            "Content-Length": str(len(file_bytes)),
        },
    )
