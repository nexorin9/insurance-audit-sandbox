"""
规则引擎性能基准测试

测试 50/100/1000 条费用明细在不同规则数量下的执行时间，
建立性能基线并输出到 benchmark_results.json。
"""

import json
import sys
import time
from pathlib import Path

# 确保 src 目录在路径中
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from engine_rules.parser import parse_rule_yaml
from engine_rules.executor import execute_rules

# ---- 数据集路径 ----
DATA_DIR = Path(__file__).parent.parent / "data"
RULES_PATH = Path(__file__).parent.parent / "src" / "engine_rules" / "rules" / "rule_examples.yaml"

# ---- 加载费用数据 ----
def load_fee_data(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def generate_1000_items(items_100: list[dict]) -> list[dict]:
    """将 100 条数据重复并微调生成 1000 条，确保规模真实"""
    import uuid
    result = []
    for i in range(10):
        for item in items_100:
            # 微调金额以避免完全相同
            new_item = dict(item)
            new_item["item_id"] = str(uuid.uuid4())
            if i > 0 and "amount" in new_item:
                # 在 ±5% 范围内波动
                import random
                new_item["amount"] = round(new_item["amount"] * (1 + random.uniform(-0.05, 0.05)), 2)
            result.append(new_item)
    return result


# ---- 加载规则 ----
def load_rules() -> list[dict]:
    """返回所有规则（可按数量切片）

    parse_rule_yaml 返回扁平规则列表，非规则集列表。
    """
    rules = parse_rule_yaml(str(RULES_PATH))
    print(f"  [load_rules] parsed {len(rules)} rules from {RULES_PATH}")
    return rules


# ---- 性能测试 ----
def benchmark(items: list[dict], rules: list[dict], iterations: int = 5) -> dict:
    """
    对给定数据集和规则集运行多次基准测试。
    Returns: {avg_ms, p50_ms, p95_ms, p99_ms}
    """
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        execute_rules(items, rules)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)

    times.sort()
    n = len(times)
    return {
        "avg_ms": round(sum(times) / n, 3),
        "p50_ms": round(times[n // 2], 3),
        "p95_ms": round(times[int(n * 0.95)], 3),
        "p99_ms": round(times[int(n * 0.99)], 3),
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
    }


# ---- 基线验证 ----
BASELINE = {
    (50, 5): 500,
    (100, 10): 1000,
    (1000, 20): 5000,
}


def check_baseline(item_count: int, rule_count: int, avg_ms: float) -> str:
    key = (item_count, rule_count)
    if key in BASELINE:
        limit = BASELINE[key]
        if avg_ms <= limit:
            return f"PASS (≤{limit}ms)"
        else:
            return f"FAIL (>{limit}ms, got {avg_ms}ms)"
    return "N/A"


# ---- 主流程 ----
def main():
    print("Loading data and rules...")

    # 加载数据
    items_50 = load_fee_data(DATA_DIR / "fee_sample_50.json")
    items_100 = load_fee_data(DATA_DIR / "fee_sample_100.json")
    items_1000 = generate_1000_items(items_100)

    # 加载规则
    all_rules = load_rules()
    print(f"Total rules loaded: {len(all_rules)}")

    # 规则集切片
    rule_sets = {
        5: all_rules[:5],
        10: all_rules[:10],
        20: all_rules,
    }

    # 测试组合
    test_configs = [
        (items_50, 50, 5, "fee_sample_50.json + 5 rules"),
        (items_50, 50, 10, "fee_sample_50.json + 10 rules"),
        (items_100, 100, 5, "fee_sample_100.json + 5 rules"),
        (items_100, 100, 10, "fee_sample_100.json + 10 rules"),
        (items_100, 100, 20, "fee_sample_100.json + 20 rules"),
        (items_1000, 1000, 5, "1000 items + 5 rules"),
        (items_1000, 1000, 10, "1000 items + 10 rules"),
        (items_1000, 1000, 20, "1000 items + 20 rules"),
    ]

    results: dict = {
        "version": "0.1.0",
        "timestamp": __import__("datetime").datetime.now().__str__(),
        "benchmarks": [],
    }

    print("\nRunning benchmarks...\n")
    print(f"{'Config':<40} {'Avg(ms)':>10} {'P50(ms)':>10} {'P95(ms)':>10} {'P99(ms)':>10} {'Baseline':>20}")
    print("-" * 100)

    for items, item_count, rule_count, label in test_configs:
        rules = rule_sets[rule_count]
        stats = benchmark(items, rules, iterations=5)
        baseline_status = check_baseline(item_count, rule_count, stats["avg_ms"])

        result_entry = {
            "label": label,
            "item_count": item_count,
            "rule_count": rule_count,
            "avg_ms": stats["avg_ms"],
            "p50_ms": stats["p50_ms"],
            "p95_ms": stats["p95_ms"],
            "p99_ms": stats["p99_ms"],
            "min_ms": stats["min_ms"],
            "max_ms": stats["max_ms"],
            "baseline": baseline_status,
        }
        results["benchmarks"].append(result_entry)

        print(f"{label:<40} {stats['avg_ms']:>10.3f} {stats['p50_ms']:>10.3f} "
              f"{stats['p95_ms']:>10.3f} {stats['p99_ms']:>10.3f} {baseline_status:>20}")

    # 写入结果
    output_path = Path(__file__).parent.parent / "benchmark_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults written to: {output_path}")

    # 汇总
    print("\n=== Baseline Summary ===")
    all_pass = True
    for entry in results["benchmarks"]:
        if "FAIL" in entry["baseline"]:
            all_pass = False
            print(f"  {entry['label']}: {entry['baseline']}")
    if all_pass:
        print("  All baselines PASSED")
    else:
        print("  Some baselines FAILED — see above")


if __name__ == "__main__":
    main()