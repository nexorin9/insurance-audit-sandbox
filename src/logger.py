"""
结构化日志系统 — JSON 格式日志输出到 logs/ 目录，支持日志轮转
"""

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from logging.handlers import RotatingFileHandler

from pythonjsonlogger import jsonlogger


# ---- 路径配置 ----
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

APP_LOG_FILE = LOGS_DIR / "app.log"
REQUEST_LOG_FILE = LOGS_DIR / "request.log"


def _build_json_formatter() -> jsonlogger.JsonFormatter:
    """构建 JSON 格式化器"""
    return jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        rename_fields={"levelname": "level", "name": "logger"},
    )


def setup_logger(name: str = "sandbox", log_file: Path = APP_LOG_FILE) -> logging.Logger:
    """配置结构化 JSON 日志器

    Args:
        name: 日志器名称
        log_file: 日志文件路径

    Returns:
        配置好的日志器
    """
    logger_ = logging.getLogger(name)
    if logger_.handlers:
        return logger_

    logger_.setLevel(logging.DEBUG)

    # JSON 格式化器
    json_fmt = _build_json_formatter()

    # 控制台处理器（彩色输出）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_fmt)
    console_handler.setLevel(logging.INFO)

    # 文件处理器（轮转）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(json_fmt)
    file_handler.setLevel(logging.DEBUG)

    logger_.addHandler(console_handler)
    logger_.addHandler(file_handler)

    return logger_


def get_logger(name: str = "sandbox") -> logging.Logger:
    """获取已配置的日志器"""
    return logging.getLogger(name)


def log_request(method: str, path: str, status_code: int, duration_ms: float) -> None:
    """记录 HTTP 请求日志（独立文件）"""
    logger = get_logger("sandbox")
    logger.info(
        "http_request",
        extra={
            "event": "http_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
    )


# ---- 全局日志器 ----
_app_logger = setup_logger("sandbox", APP_LOG_FILE)
_request_logger = setup_logger("sandbox.request", REQUEST_LOG_FILE)


def get_request_logger() -> logging.Logger:
    """获取请求日志器"""
    return _request_logger