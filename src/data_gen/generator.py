"""
费用数据合成器 — 生成脱敏费用明细数据
保留业务语义，覆盖边界场景
"""

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

CATEGORIES = ["药品", "耗材", "手术", "检查", "床位"]
INJECTION_TYPES = ["中药注射剂", "西药注射剂", None]
PROCEDURE_CODES = [
    "P001", "P002", "P003", "P004", "P005",
    "S001", "S002", "S003",
    "C001", "C002",
    "B001", "B002",
]


class FeeDataGenerator:
    """费用数据生成器"""

    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

    def generate_item(self, include_boundary: bool = False) -> dict:
        """生成单条费用明细"""
        category = self._rng.choice(CATEGORIES)

        item = {
            "item_id": str(uuid.uuid4()),
            "category": category,
        }

        if category == "药品":
            item["amount"] = self._rng.uniform(10.0, 2000.0)
            item["unit_price"] = round(self._rng.uniform(5.0, 500.0), 2)
            item["quantity"] = self._rng.randint(1, 30)
            item["injection_type"] = self._rng.choice(INJECTION_TYPES)
            # 中药注射剂单独标注
            if item["injection_type"] == "中药注射剂" and item["amount"] > 500:
                item["_high_risk"] = True
        elif category == "耗材":
            item["amount"] = self._rng.uniform(50.0, 5000.0)
            item["unit_price"] = round(self._rng.uniform(20.0, 2000.0), 2)
            item["quantity"] = self._rng.randint(1, 10)
            item["material_markup_rate"] = round(self._rng.uniform(0.0, 0.30), 4)
            if item["material_markup_rate"] > 0.15:
                item["_high_risk"] = True
        elif category == "手术":
            item["amount"] = self._rng.uniform(500.0, 30000.0)
            item["unit_price"] = round(self._rng.uniform(200.0, 10000.0), 2)
            item["quantity"] = 1
            item["procedure_code"] = self._rng.choice(PROCEDURE_CODES[:3])
            item["days_admitted"] = self._rng.randint(1, 30)
            if item["days_admitted"] < 3 and item["procedure_code"].startswith("S"):
                item["_high_risk"] = True  # 分解住院嫌疑
        elif category == "检查":
            item["amount"] = self._rng.uniform(100.0, 3000.0)
            item["unit_price"] = round(self._rng.uniform(50.0, 1500.0), 2)
            item["quantity"] = self._rng.randint(1, 5)
        else:  # 床位
            item["amount"] = self._rng.uniform(30.0, 300.0)
            item["unit_price"] = round(self._rng.uniform(20.0, 150.0), 2)
            item["quantity"] = self._rng.randint(1, 30)
            item["days_admitted"] = self._rng.randint(1, 60)

        # 修正 amount 与 unit_price * quantity 的一致性（允许浮点误差）
        if "unit_price" in item and "quantity" in item:
            computed = round(item["unit_price"] * item["quantity"], 2)
            item["amount"] = round(computed * self._rng.uniform(0.9, 1.1), 2)

        return item

    def generate_boundary_items(self) -> list[dict]:
        """生成边界场景费用明细"""
        items = []

        # 边界1：加价率临界值 0.15
        for rate in [0.15, 0.1501, 0.16, 0.20, 0.25]:
            item = {
                "item_id": str(uuid.uuid4()),
                "category": "耗材",
                "amount": round(1000.0 * rate, 2),
                "unit_price": round(1000.0, 2),
                "quantity": 1,
                "material_markup_rate": round(rate, 4),
            }
            if rate > 0.15:
                item["_high_risk"] = True
            items.append(item)

        # 边界2：剂量异常（quantity 异常大）
        item = {
            "item_id": str(uuid.uuid4()),
            "category": "药品",
            "amount": 99999.0,
            "unit_price": 99.99,
            "quantity": 1001,
            "injection_type": "西药注射剂",
        }
        item["_high_risk"] = True
        items.append(item)

        # 边界3：unit_price 异常高
        items.append({
            "item_id": str(uuid.uuid4()),
            "category": "耗材",
            "amount": 99999.0,
            "unit_price": 99999.0,
            "quantity": 1,
            "material_markup_rate": 0.20,
            "_high_risk": True,
        })

        # 边界4：分解住院嫌疑（手术类但住院天数极少）
        for days in [1, 2]:
            items.append({
                "item_id": str(uuid.uuid4()),
                "category": "手术",
                "amount": round(5000.0 * days, 2),
                "unit_price": round(5000.0, 2),
                "quantity": 1,
                "procedure_code": "S001",
                "days_admitted": days,
                "_high_risk": True,
            })

        # 边界5：中药注射剂超限
        items.append({
            "item_id": str(uuid.uuid4()),
            "category": "药品",
            "amount": 1500.0,
            "unit_price": 500.0,
            "quantity": 3,
            "injection_type": "中药注射剂",
            "_high_risk": True,
        })

        # 边界6：跨科室费用组合（同一患者触发多规则交叉）
        # 组合：耗材(加价率微超) + 手术(住院天数少) + 药品(中药注射剂)
        patient_id = str(uuid.uuid4())
        items.extend([
            {
                "item_id": str(uuid.uuid4()),
                "category": "耗材",
                "amount": 1150.0,
                "unit_price": 1000.0,
                "quantity": 1,
                "material_markup_rate": 0.1501,  # 微超临界值
                "_high_risk": True,
                "_patient_id": patient_id,
                "_cross_category": True,
            },
            {
                "item_id": str(uuid.uuid4()),
                "category": "手术",
                "amount": 8000.0,
                "unit_price": 8000.0,
                "quantity": 1,
                "procedure_code": "S002",
                "days_admitted": 2,  # 分解住院嫌疑
                "_high_risk": True,
                "_patient_id": patient_id,
                "_cross_category": True,
            },
            {
                "item_id": str(uuid.uuid4()),
                "category": "药品",
                "amount": 800.0,
                "unit_price": 200.0,
                "quantity": 4,
                "injection_type": "中药注射剂",
                "_high_risk": True,
                "_patient_id": patient_id,
                "_cross_category": True,
            },
        ])

        # 边界7：加价率临界精准值（0.15 精确等于）
        items.append({
            "item_id": str(uuid.uuid4()),
            "category": "耗材",
            "amount": 1150.0,
            "unit_price": 1000.0,
            "quantity": 1,
            "material_markup_rate": 0.1500,  # 精确等于临界值
            "_boundary_exact": True,
        })

        # 边界8： quantity 边界临界值（quantity = 1，但 amount 异常）
        items.append({
            "item_id": str(uuid.uuid4()),
            "category": "耗材",
            "amount": 25000.0,
            "unit_price": 25000.0,
            "quantity": 1,
            "material_markup_rate": 0.20,
            "_high_risk": True,
        })

        # 边界9：检查类与药品组合（处方费用异常）
        items.append({
            "item_id": str(uuid.uuid4()),
            "category": "检查",
            "amount": 5000.0,
            "unit_price": 5000.0,
            "quantity": 1,
        })
        items.append({
            "item_id": str(uuid.uuid4()),
            "category": "药品",
            "amount": 3000.0,
            "unit_price": 1000.0,
            "quantity": 3,
            "injection_type": "西药注射剂",
        })

        # 边界10：床位费超长住院（days_admitted 极大，测试边界）
        items.append({
            "item_id": str(uuid.uuid4()),
            "category": "床位",
            "amount": 18000.0,
            "unit_price": 60.0,
            "quantity": 300,
            "days_admitted": 300,
        })

        # 边界11：药品数量为零边界（quantity=0 是否被规则接受）
        items.append({
            "item_id": str(uuid.uuid4()),
            "category": "药品",
            "amount": 0.0,
            "unit_price": 100.0,
            "quantity": 0,
            "injection_type": None,
        })

        # 边界12：手术类无 procedure_code（字段缺失）
        items.append({
            "item_id": str(uuid.uuid4()),
            "category": "手术",
            "amount": 12000.0,
            "unit_price": 12000.0,
            "quantity": 1,
            "days_admitted": 5,
            # procedure_code 故意缺失
        })

        return items

    def generate(self, count: int, include_boundary: bool = True) -> list[dict]:
        """生成指定数量的费用明细"""
        items = [self.generate_item() for _ in range(count)]
        if include_boundary:
            items.extend(self.generate_boundary_items())
        return items


def main():
    parser = argparse.ArgumentParser(description="费用数据合成器")
    parser.add_argument("--count", type=int, default=50, help="生成费用明细条数")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    parser.add_argument("--no-boundary", action="store_true", help="不包含边界场景")
    parser.add_argument("--boundary-only", action="store_true", help="仅生成边界场景（20条极端边界案例）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    if args.output is None:
        output_path = Path(__file__).parent.parent.parent / "data" / "fee_sample.json"
    else:
        output_path = Path(args.output)

    gen = FeeDataGenerator(seed=args.seed)
    if args.boundary_only:
        items = gen.generate_boundary_items()
        if args.output is None:
            output_path = Path(__file__).parent.parent.parent / "data" / "fee_sample_boundary.json"
    else:
        items = gen.generate(count=args.count, include_boundary=not args.no_boundary)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(items)} fee items -> {output_path}")
    high_risk = sum(1 for it in items if it.get("_high_risk"))
    print(f"High-risk items: {high_risk}")


if __name__ == "__main__":
    main()