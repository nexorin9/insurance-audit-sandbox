# 医保飞检规则演练沙盘

让信息科/医保办在脱敏数据上模拟飞检过程，提前发现本院高风险费用项，系统输出高风险费用项清单及整改建议报告（PDF/Word）。

## 目标岗位

- **信息科**：演练操作者
- **医保办**：报告使用者
- **信息科科长**：监督进度

## 触发场景

每月例行合规检查前，或收到医保局预警后，选择规则集、导入脱敏费用数据，运行演练，输出整改建议报告。

## 最小数据契约

- **输入**：费用明细 JSON + 规则集 YAML
- **输出**：演练结果 JSON + PDF/Word 整改建议报告

## 技术栈

- Python 规则引擎（核心）
- Node.js/TypeScript 前端 SPA
- FastAPI
- SQLite
- Docker

## 核心模块

- 规则引擎（engine）
- 演练前端（frontend SPA）
- API 服务
- 报告生成
- 样例数据合成器
- 配置管理与部署

## 目录结构

```
insurance-audit-sandbox/
├── src/
│   ├── engine/          # 规则引擎（parser/executor/scorer/condition_ops）
│   ├── api/             # FastAPI 服务（routes/models/db）
│   ├── frontend/        # React SPA（Vite + TypeScript）
│   ├── report/          # 报告生成（PDF/Word）
│   └── data_gen/        # 样例数据合成器
├── data/                # 费用数据样例
│   ├── fee_sample_50.json   # 50 条样例费用数据
│   └── fee_sample_100.json  # 100 条样例费用数据
├── templates/           # 报告模板
├── rules/               # 规则集 YAML
│   ├── zhongyao_injection_limit.yaml   # 中药注射剂限制规则
│   ├── material_markup_limit.yaml      # 耗材加价率超限规则
│   ├── decomposition_suspicion.yaml     # 分解住院嫌疑规则
│   └── rules_index.yaml                # 规则集索引
├── config.yaml           # 演练参数配置
├── .env.example          # 环境变量示例
├── requirements.txt      # Python 依赖
├── package.json          # Node 依赖
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 安装

### 前置条件

- Docker >= 20.10
- Docker Compose >= 2.0
- Python >= 3.10（本地开发可选）
- Node.js >= 18（本地开发可选）

### Docker 部署（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd insurance-audit-sandbox

# 启动服务
docker-compose up
```

服务启动后：
- API 服务：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 前端页面：http://localhost:5173

### 本地开发

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 安装前端依赖
cd src/frontend
npm install

# 3. 启动前端开发服务器
npm run dev

# 4. 另起终端，启动 API 服务
cd ../..
uvicorn src.api.main:app --reload --port 8000
```

## 配置

### config.yaml

演练参数在 `config.yaml` 中定义：

```yaml
database:
  path: "data/sandbox.db"        # SQLite 数据库路径

log_level: "INFO"                 # 日志级别：DEBUG/INFO/WARNING

sandbox:
  default_rule_set: "zhongyao_injection_limit"
  risk_threshold_70: 70          # 高风险阈值
  risk_threshold_90: 90          # 极高风险阈值
  report_format: "pdf"           # 默认报告格式：pdf/docx
```

### 环境变量（.env.example）

```bash
cp .env.example .env
# 编辑 .env 填写真实值（可选）
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| DATABASE_PATH | SQLite 数据库路径 | data/sandbox.db |
| LOG_LEVEL | 日志级别 | INFO |
| API_PORT | API 服务端口 | 8000 |

## 使用

### 演练执行流程

**Step 1：选择规则集**

在「规则集管理」页面查看可用规则集（中药注射剂限制 / 耗材加价率超限 / 分解住院嫌疑），或上传自定义规则 YAML。

**Step 2：上传费用数据**

在「演练执行」页面，上传费用明细 JSON 文件（格式见 `data/fee_sample_50.json`），或使用内置合成数据。

**Step 3：执行演练**

点击「执行演练」，系统将：
1. 加载选定规则集
2. 遍历每条费用明细，执行规则匹配
3. 计算风险评分，生成风险分布统计
4. 持久化演练结果到 SQLite

**Step 4：查看结果**

演练完成后，在结果页面查看：
- 高风险费用项清单（含 item_id、类别、金额、风险分数）
- TOP 高风险类别汇总
- 风险分布图表

**Step 5：下载报告**

点击「生成报告」，选择 PDF 或 Word 格式，下载含整改建议的整改建议报告。

### API 调用示例

```bash
# 健康检查
curl http://localhost:8000/health

# 列出规则集
curl http://localhost:8000/rules

# 执行演练
curl -X POST http://localhost:8000/sandbox/run \
  -H "Content-Type: application/json" \
  -d '{"rule_set_id": "zhongyao_injection_limit", "fee_items": [...] }'

# 生成报告
curl -X POST http://localhost:8000/reports/generate?run_id=<run_id>&format=pdf \
  -o report.pdf
```

## 验收

### 演示路径

**目标**：使用合成数据完成端到端演练，验证 PDF 报告内容完整。

**步骤**：

```bash
# 1. 启动服务
docker-compose up

# 2. 等待服务就绪
curl http://localhost:8000/health
# 期望返回：{"status": "ok", "timestamp": "..."}

# 3. 执行演练（使用内置 50 条样例数据）
curl -X POST http://localhost:8000/sandbox/run \
  -H "Content-Type: application/json" \
  -d '{
    "rule_set_id": "zhongyao_injection_limit",
    "fee_items": <读取 data/fee_sample_50.json 的内容>
  }'
# 记录返回的 run_id

# 4. 生成 PDF 报告
curl -X POST "http://localhost:8000/reports/generate?run_id=<run_id>&format=pdf" \
  -o report.pdf

# 5. 验证 PDF 内容
# - 报告封面含演练名称、规则集版本、执行时间戳
# - 高风险项表格含 item_id、category、amount、risk_score
# - TOP 高风险类别汇总
# - 整改建议节

# 6. 停止服务
docker-compose down
```

### 验收检查清单

- [ ] `docker-compose up` 成功启动，无报错
- [ ] `GET /health` 返回 `status: ok`
- [ ] `GET /rules` 返回至少 3 个内置规则集
- [ ] 演练执行后 `hit_count > 0`（合成数据含边界场景）
- [ ] PDF 报告可下载，内容含高风险项清单
- [ ] Dashboard 列表显示演练历史记录

## 安全扩展

当前 API 鉴权为 **stub 模式**（开发/演示用），生产部署前请按以下方式替换为真实鉴权。

### 当前实现

- 检查 `Authorization: Bearer <token>` 或 `X-API-Key` header
- 若未配置 `API_AUTH_KEY` 环境变量，**默认放行**（开发模式）并记录 warning 日志
- `/health`、`/ready`、`/docs`、`/openapi.json`、`/redoc` 端点豁免鉴权

### 启用鉴权

```bash
# 设置 API 密钥（生产模式）
export API_AUTH_KEY="your-secret-key-here"
export API_AUTH_DISABLED=""  # 确保非空，启用鉴权

# 或在 .env 中配置
echo 'API_AUTH_KEY=your-secret-key-here' >> .env
echo 'API_AUTH_DISABLED=' >> .env
```

### 升级为真实 JWT 验证

1. 安装 PyJWT：

```bash
pip install PyJWT
```

2. 修改 `src/api/middleware/auth.py` 中的 `_verify_token` 函数：

```python
import jwt
from datetime import datetime, timezone

def _verify_token(token: str) -> bool:
    """验证 JWT token（替换本函数为真实 JWT 验证）"""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,          # 从环境变量 JWT_SECRET 读取
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]}
        )
        # 可在此处补充业务逻辑：检查用户权限、角色等
        return True
    except jwt.ExpiredSignatureError:
        logger.warning("Token 已过期")
        return False
    except jwt.InvalidTokenError as e:
        logger.warning(f"无效 Token: {e}")
        return False
```

3. 在 `src/api/main.py` 中注册中间件前，配置 JWT 密钥：

```python
import os
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
```

### 生产部署检查清单

- [ ] `API_AUTH_KEY` 或 `JWT_SECRET` 已配置（禁止使用默认值）
- [ ] `API_AUTH_DISABLED` 未设置（确保鉴权启用）
- [ ] 回调 `/health` 和 `/ready` 端点已豁免（无需 token 即可健康检查）
- [ ] 所有业务端点（`/rules`、`/sandbox/*`、`/reports/*`）均需要有效 token

## 许可证

MIT License

---

## 支持作者

如果您觉得这个项目对您有帮助，欢迎打赏支持！
Wechat:gdgdmp
![Buy Me a Coffee](buymeacoffee.png)

**Buy me a coffee (crypto)**

| 币种 | 地址 |
|------|------|
| BTC | `bc1qc0f5tv577z7yt59tw8sqaq3tey98xehy32frzd` |
| ETH / USDT | `0x3b7b6c47491e4778157f0756102f134d05070704` |
| SOL | `6Xuk373zc6x6XWcAAuqvbWW92zabJdCmN3CSwpsVM6sd` |