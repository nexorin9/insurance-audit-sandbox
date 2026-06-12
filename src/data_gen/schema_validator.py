"""
费用字段 Schema 验证器
验证合成数据是否符合 fee_schema.yaml 规范
"""

import json
import re
from pathlib import Path
from typing import Any

import yaml


class SchemaValidationError(Exception):
    """Schema 验证错误"""

    def __init__(self, field: str, message: str, item_id: str = None):
        self.field = field
        self.item_id = item_id
        super().__init__(f"item_id={item_id}: {field} - {message}")


class FeeSchemaValidator:
    """费用数据 Schema 验证器"""

    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )

    def __init__(self, schema_path: str | Path = None):
        if schema_path is None:
            schema_path = Path(__file__).parent / "fee_schema.yaml"
        with open(schema_path, encoding="utf-8") as f:
            self.schema = yaml.safe_load(f)
        self.fields = self.schema.get("fields", {})
        self.internal_fields = self.schema.get("internal_fields", {})

    def validate_item(self, item: dict) -> list[SchemaValidationError]:
        """验证单条费用明细，返回错误列表（空列表表示通过）"""
        errors = []
        item_id = item.get("item_id", "unknown")
        category = item.get("category")

        # 验证必填字段
        for field_name, field_def in self.fields.items():
            if field_def.get("required", False):
                if field_name not in item:
                    errors.append(
                        SchemaValidationError(field_name, "missing required field", item_id)
                    )

        # 验证 item_id 格式
        if "item_id" in item:
            if not self.UUID_PATTERN.match(str(item["item_id"])):
                errors.append(
                    SchemaValidationError(
                        "item_id", "must be a valid UUID format", item_id
                    )
                )

        # 验证 category
        if "category" in item:
            allowed = self.fields["category"]["enum"]
            if item["category"] not in allowed:
                errors.append(
                    SchemaValidationError(
                        "category",
                        f"must be one of {allowed}, got '{item['category']}'",
                        item_id,
                    )
                )

        # 验证数值字段
        for field_name in ["amount", "unit_price", "quantity"]:
            if field_name in item:
                value = item[field_name]
                constraints = self.fields.get(field_name, {}).get("constraints", {})

                if "gt" in constraints and value <= constraints["gt"]:
                    errors.append(
                        SchemaValidationError(
                            field_name,
                            f"must be > {constraints['gt']}, got {value}",
                            item_id,
                        )
                    )
                if "gte" in constraints and value < constraints["gte"]:
                    errors.append(
                        SchemaValidationError(
                            field_name,
                            f"must be >= {constraints['gte']}, got {value}",
                            item_id,
                        )
                    )
                if "lte" in constraints and value > constraints["lte"]:
                    errors.append(
                        SchemaValidationError(
                            field_name,
                            f"must be <= {constraints['lte']}, got {value}",
                            item_id,
                        )
                    )

        # 验证 material_markup_rate（耗材类特有）
        if "material_markup_rate" in item:
            rate = item["material_markup_rate"]
            if rate is not None:
                if not (0 <= rate <= 1):
                    errors.append(
                        SchemaValidationError(
                            "material_markup_rate",
                            f"must be between 0 and 1, got {rate}",
                            item_id,
                        )
                    )
            if category and category != "耗材":
                errors.append(
                    SchemaValidationError(
                        "material_markup_rate",
                        f"field only valid for 耗材 category, got {category}",
                        item_id,
                    )
                )

        # 验证 injection_type（药品类特有）
        if "injection_type" in item:
            it = item["injection_type"]
            if it is not None:
                allowed = self.fields["injection_type"]["enum"]
                if it not in allowed:
                    errors.append(
                        SchemaValidationError(
                            "injection_type",
                            f"must be one of {allowed}, got '{it}'",
                            item_id,
                        )
                    )
            if category and category != "药品":
                errors.append(
                    SchemaValidationError(
                        "injection_type",
                        f"field only valid for 药品 category, got {category}",
                        item_id,
                    )
                )

        # 验证 procedure_code（手术类特有）
        if "procedure_code" in item:
            if category and category != "手术":
                errors.append(
                    SchemaValidationError(
                        "procedure_code",
                        f"field only valid for 手术 category, got {category}",
                        item_id,
                    )
                )

        # 验证 days_admitted（手术/床位类特有）
        if "days_admitted" in item:
            if category and category not in ("手术", "床位"):
                errors.append(
                    SchemaValidationError(
                        "days_admitted",
                        f"field only valid for 手术/床位 category, got {category}",
                        item_id,
                    )
                )
            if item["days_admitted"] is not None and item["days_admitted"] <= 0:
                errors.append(
                    SchemaValidationError(
                        "days_admitted",
                        f"must be > 0, got {item['days_admitted']}",
                        item_id,
                    )
                )

        return errors

    def validate(self, items: list[dict]) -> dict[str, Any]:
        """
        验证费用数据列表
        返回验证结果：{valid: bool, total: int, valid_count: int, errors: []}
        """
        total = len(items)
        all_errors = []
        valid_count = 0

        for item in items:
            errors = self.validate_item(item)
            if errors:
                all_errors.extend(errors)
            else:
                valid_count += 1

        return {
            "valid": len(all_errors) == 0,
            "total": total,
            "valid_count": valid_count,
            "invalid_count": total - valid_count,
            "errors": [
                {"field": e.field, "message": str(e), "item_id": e.item_id}
                for e in all_errors
            ],
        }


def main():
    """命令行验证工具"""
    import argparse

    parser = argparse.ArgumentParser(description="验证费用数据 Schema")
    parser.add_argument("input_file", help="输入 JSON 文件路径")
    parser.add_argument("--schema", default=None, help="Schema 文件路径")
    args = parser.parse_args()

    with open(args.input_file, encoding="utf-8") as f:
        items = json.load(f)

    validator = FeeSchemaValidator(args.schema)
    result = validator.validate(items)

    print(f"Total: {result['total']}")
    print(f"Valid: {result['valid_count']}")
    print(f"Invalid: {result['invalid_count']}")

    if result["errors"]:
        print("\nErrors:")
        for err in result["errors"][:10]:  # 最多显示 10 个错误
            print(f"  - {err['item_id']}: {err['field']} - {err['message']}")
        if len(result["errors"]) > 10:
            print(f"  ... and {len(result['errors']) - 10} more errors")

    if result["valid"]:
        print("\nValidation PASSED")
    else:
        print("\nValidation FAILED")
        exit(1)


if __name__ == "__main__":
    main()