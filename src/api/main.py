"""
API 服务 — FastAPI 入口
"""

import logging
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import HealthResponse, ReadyResponse
from .routes.rules import router as rules_router
from .routes.sandbox import router as sandbox_router
from .routes.reports import router as reports_router
from .routes.compare import router as compare_router
from .middleware.auth import AuthMiddleware
from src.logger import setup_logger, get_logger, log_request


# ---- 日志配置 ----
logger = setup_logger("sandbox")


# ---- 规则集扫描 ----
RULES_DIR = __import__("pathlib").Path(__file__).parent.parent / "engine" / "rules"

def _scan_rule_sets() -> int:
    """扫描 rules/ 目录下所有规则集 YAML 文件数量"""
    if not RULES_DIR.exists():
        return 0
    return len(list(RULES_DIR.glob("*.yaml")))


_rules_loaded = _scan_rule_sets()


# ---- 启动/关闭生命周期 ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Insurance Audit Sandbox API 启动")
    yield
    logger.info("Insurance Audit Sandbox API 关闭")


# ---- FastAPI 应用 ----
app = FastAPI(
    title="Insurance Audit Sandbox",
    version="0.1.0",
    description="医保飞检规则演练沙盘 API",
    lifespan=lifespan,
)

# ---- CORS 配置 ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 鉴权中间件 ----
app.add_middleware(AuthMiddleware)


# ---- 请求日志中间件 ----
@app.middleware("http")
async def log_requests(request: Request, call_next):
    method = request.method
    path = request.url.path
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    log_request(method, path, response.status_code, duration_ms)
    return response


# ---- 健康检查端点 ----
@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health():
    """健康检查端点 — 验证 API 服务进程是否存活。

    可用于 Kubernetes livenessProbe 或负载均衡器探活。
    此端点不需要鉴权。

    Returns:
        HealthResponse: status="ok" 且包含当前服务器时间戳。
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ---- 就绪检查端点 ----
@app.get("/ready", response_model=ReadyResponse, tags=["系统"])
async def ready():
    """就绪检查端点 — 验证 API 服务是否已完成初始化（规则集加载）。

    可用于 Kubernetes readinessProbe。
    此端点不需要鉴权。

    Returns:
        ReadyResponse: status="ready" 且包含已扫描到的规则集数量。
    """
    return ReadyResponse(
        status="ready",
        rules_loaded=_rules_loaded,
    )

# ---- 规则集路由 ----
app.include_router(rules_router)

# ---- 演练路由 ----
app.include_router(sandbox_router)

# ---- 报告路由 ----
app.include_router(reports_router)

# ---- 对比路由 ----
app.include_router(compare_router)