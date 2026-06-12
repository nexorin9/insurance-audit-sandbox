"""
API 鉴权中间件 stub

功能：
- 检查 Authorization header（Bearer token 或 X-API-Key）
- 开发模式下降级处理：若未配置鉴权密钥，默认放行并记录 warning
- /health 和 /ready 端点豁免鉴权

扩展方式：
- 替换 _verify_token 为真实 JWT 验证逻辑（依赖 PyJWT）
- 或接入外部 IAM/OAuth2 服务
"""

import logging
import os
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("api.auth")


# ---- 配置项 ----
API_KEY: Optional[str] = os.getenv("API_AUTH_KEY")
AUTH_DISABLED: bool = os.getenv("API_AUTH_DISABLED", "").lower() in ("1", "true", "yes")


# ---- Token 验证函数（stub）----
def _verify_token(token: str) -> bool:
    """
    验证 token 有效性。

    当前实现：仅检查是否与 API_AUTH_KEY 环境变量匹配。
    扩展方式：替换为本函数内调用 PyJWT decode 或外部 IAM 验证。
    """
    if not API_KEY:
        return False
    return token == API_KEY


# ---- 豁免路径 ----
EXEMPT_PATHS = {"/health", "/ready", "/docs", "/openapi.json", "/redoc"}


# ---- 鉴权中间件 ----
class AuthMiddleware(BaseHTTPMiddleware):
    """API 鉴权中间件"""

    async def dispatch(self, request: Request, call_next):
        # 豁免路径直接放行
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # 开发模式：未配置密钥时放行
        if AUTH_DISABLED or not API_KEY:
            logger.warning(
                "API_AUTH_KEY 未配置，鉴权已禁用（开发模式）"
            )
            return await call_next(request)

        # 获取 Authorization header
        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")

        token: Optional[str] = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        elif api_key:
            token = api_key

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "缺少 Authorization header（Bearer token）或 X-API-Key"},
            )

        if not _verify_token(token):
            return JSONResponse(
                status_code=403,
                content={"detail": "无效的 token 或 API Key"},
            )

        return await call_next(request)