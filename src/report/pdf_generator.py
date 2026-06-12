"""
报告生成 — PDF 整改建议报告
使用 reportlab 生成结构化 PDF 整改建议报告。
"""

import io
import logging
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ---- 页面样式常量 ----
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 20 * mm


class PdfReportGenerator:
    """PDF 整改建议报告生成器"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._build_styles()

    def _build_styles(self):
        """构建自定义段落样式"""
        self.styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=self.styles["Heading1"],
            fontSize=18,
            spaceAfter=12 * mm,
            alignment=1,  # 居中
        ))
        self.styles.add(ParagraphStyle(
            name="SectionTitle",
            parent=self.styles["Heading2"],
            fontSize=13,
            spaceBefore=8 * mm,
            spaceAfter=4 * mm,
            textColor=colors.HexColor("#1a3a5c"),
        ))
        self.styles.add(ParagraphStyle(
            name="Body",
            parent=self.styles["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=4 * mm,
        ))
        self.styles.add(ParagraphStyle(
            name="Small",
            parent=self.styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.grey,
        ))

    def generate(
        self,
        run_id: str,
        timestamp: str,
        rule_set_version: str,
        total_items: int,
        hit_items: list[dict],
        risk_distribution: dict[str, dict],
        top_risk_categories: list[dict],
        output_path: str | None = None,
    ) -> bytes:
        """
        生成 PDF 报告。

        Args:
            run_id: 演练记录ID
            timestamp: 执行时间（ISO 8601）
            rule_set_version: 规则集版本
            total_items: 总费用条数
            hit_items: 命中费用明细列表
            risk_distribution: 风险分布字典
            top_risk_categories: TOP 高风险类别列表
            output_path: 若指定则写入文件；否则返回 bytes

        Returns:
            PDF 字节流
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
        )

        story: list[Any] = []

        # ---- 封面 ----
        story.append(Spacer(1, 15 * mm))
        story.append(Paragraph("医保飞检规则演练整改建议报告", self.styles["ReportTitle"]))
        story.append(Spacer(1, 5 * mm))

        # 元信息表
        meta_data = [
            ["演练记录ID", run_id],
            ["执行时间", timestamp],
            ["规则集版本", rule_set_version],
            ["费用总条数", str(total_items)],
            ["高风险项数量", str(len(hit_items))],
        ]
        meta_table = Table(meta_data, colWidths=[50 * mm, 100 * mm])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f0f7")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 4 * mm),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10 * mm))

        # ---- 高风险项清单 ----
        story.append(Paragraph("一、高风险项清单", self.styles["SectionTitle"]))

        if not hit_items:
            story.append(Paragraph("本次演练未发现高风险项。", self.styles["Body"]))
        else:
            # 表头
            header = ["费用ID", "类别", "金额", "风险分", "规则名称", "匹配条件"]
            rows = [header]
            for item in hit_items:
                rows.append([
                    str(item.get("item_id", "")),
                    str(item.get("category", "")),
                    f"¥{item.get('amount', 0):.2f}",
                    f"{item.get('risk_score', 0):.1f}",
                    str(item.get("name", "")),
                    str(item.get("matched_condition", "")),
                ])

            hit_table = Table(rows, colWidths=[35 * mm, 20 * mm, 22 * mm, 18 * mm, 30 * mm, 35 * mm])
            hit_table.setStyle(TableStyle([
                # 表头样式
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                # 数据行样式
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
                ("PADDING", (0, 0), (-1, -1), 3 * mm),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),  # 金额右对齐
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),  # 风险分右对齐
                # 高风险标红（risk_score >= 70）
                ("TEXTCOLOR", (3, 1), (3, -1), colors.HexColor("#c0392b")),
            ]))
            story.append(hit_table)
            story.append(Spacer(1, 6 * mm))

        # ---- TOP 高风险类别汇总 ----
        story.append(Paragraph("二、TOP 高风险类别", self.styles["SectionTitle"]))

        if not top_risk_categories:
            story.append(Paragraph("无高风险类别数据。", self.styles["Body"]))
        else:
            cat_header = ["类别", "命中次数", "平均风险分", "风险金额合计"]
            cat_rows = [cat_header]
            for cat in top_risk_categories:
                cat_rows.append([
                    str(cat.get("category", "")),
                    str(cat.get("hit_count", 0)),
                    f"{cat.get('avg_score', 0):.1f}",
                    f"¥{cat.get('total_amount', 0):.2f}",
                ])

            cat_table = Table(cat_rows, colWidths=[40 * mm, 30 * mm, 35 * mm, 35 * mm])
            cat_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#e8f0f7")]),
                ("PADDING", (0, 0), (-1, -1), 4 * mm),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]))
            story.append(cat_table)
            story.append(Spacer(1, 6 * mm))

        # ---- 整改建议 ----
        story.append(Paragraph("三、整改建议", self.styles["SectionTitle"]))
        suggestions = self._generate_suggestions(top_risk_categories, risk_distribution)
        for sugg in suggestions:
            story.append(Paragraph(f"• {sugg}", self.styles["Body"]))

        # ---- 页脚 ----
        story.append(Spacer(1, 10 * mm))
        footer_text = (
            f"生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            f"　　演练ID：{run_id}"
        )
        story.append(Paragraph(footer_text, self.styles["Small"]))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info("PDF 报告已生成: %s", output_path)

        return pdf_bytes

    def _generate_suggestions(
        self,
        top_risk_categories: list[dict],
        risk_distribution: dict,
    ) -> list[str]:
        """根据风险分布生成整改建议"""
        suggestions = []

        for cat in (top_risk_categories or []):
            cat_name = cat.get("category", "未知类别")
            avg_score = cat.get("avg_score", 0)
            hit_count = cat.get("hit_count", 0)

            if avg_score >= 80:
                level = "高危"
            elif avg_score >= 60:
                level = "中高危"
            elif avg_score >= 40:
                level = "中危"
            else:
                level = "低危"

            sugg = (
                f"【{cat_name}】风险等级：{level}，命中 {hit_count} 条，"
                f"平均风险分 {avg_score:.1f}。建议立即组织科室会诊，"
                f"核查费用明细是否合规，及时提交整改说明。"
            )
            suggestions.append(sugg)

        # 兜底建议
        if not suggestions:
            suggestions.append("本次演练未发现明显违规项，建议持续监控费用变化趋势。")

        return suggestions
