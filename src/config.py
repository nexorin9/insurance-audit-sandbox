"""
配置管理模块
加载并验证 config.yaml 配置
"""

import os
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("config")


class Config:
    """配置管理类"""

    _instance = None
    _config: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._config:
            self.load()

    def load(self, config_path: str | None = None) -> None:
        """加载配置文件"""
        if config_path is None:
            # 相对于项目根目录查找 config.yaml
            config_path = Path(__file__).parent.parent / "config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            logger.warning("配置文件不存在: %s，使用默认配置", config_path)
            self._config = self._default_config()
            return

        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        self._validate()
        logger.info("配置文件加载成功: %s", config_path)

    def _default_config(self) -> dict:
        """默认配置"""
        return {
            "database": {"path": "data/sandbox.db", "retention_count": 100},
            "log_level": "INFO",
            "sandbox": {
                "default_rule_set": "zhongyao_injection_limit",
                "risk_threshold_70": 70,
                "risk_threshold_90": 90,
                "report_format": "pdf",
            },
            "api": {"port": 8000, "host": "0.0.0.0", "timeout": 30},
            "frontend": {"api_base_url": "http://localhost:8000"},
        }

    def _validate(self) -> None:
        """验证配置项"""
        errors = []

        # database
        db = self._config.get("database", {})
        if not isinstance(db.get("path"), str):
            errors.append("database.path 须为字符串")
        retention = db.get("retention_count", 100)
        if not isinstance(retention, int) or retention < 0:
            errors.append("database.retention_count 须为非负整数")

        # log_level
        log_level = self._config.get("log_level", "INFO")
        if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            errors.append("log_level 须为 DEBUG/INFO/WARNING/ERROR 之一")

        # sandbox
        sandbox = self._config.get("sandbox", {})
        risk_70 = sandbox.get("risk_threshold_70", 70)
        if not isinstance(risk_70, (int, float)) or not (0 <= risk_70 <= 100):
            errors.append("sandbox.risk_threshold_70 须为 0-100 数值")
        risk_90 = sandbox.get("risk_threshold_90", 90)
        if not isinstance(risk_90, (int, float)) or not (0 <= risk_90 <= 100):
            errors.append("sandbox.risk_threshold_90 须为 0-100 数值")
        report_format = sandbox.get("report_format", "pdf")
        if report_format not in ("pdf", "docx"):
            errors.append("sandbox.report_format 须为 pdf/docx 之一")

        # api
        api = self._config.get("api", {})
        port = api.get("port", 8000)
        if not isinstance(port, int) or not (1 <= port <= 65535):
            errors.append("api.port 须为 1-65535 整数")
        timeout = api.get("timeout", 30)
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append("api.timeout 须为正整数")

        if errors:
            raise ValueError("配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors))

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项（支持点号分隔的路径，如 'database.path'）"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    @property
    def database_path(self) -> str:
        return self.get("database.path", "data/sandbox.db")

    @property
    def retention_count(self) -> int:
        return self.get("database.retention_count", 100)

    @property
    def log_level(self) -> str:
        return self.get("log_level", "INFO")

    @property
    def default_rule_set(self) -> str:
        return self.get("sandbox.default_rule_set", "zhongyao_injection_limit")

    @property
    def risk_threshold_70(self) -> float:
        return self.get("sandbox.risk_threshold_70", 70.0)

    @property
    def risk_threshold_90(self) -> float:
        return self.get("sandbox.risk_threshold_90", 90.0)

    @property
    def report_format(self) -> str:
        return self.get("sandbox.report_format", "pdf")

    @property
    def api_port(self) -> int:
        return self.get("api.port", 8000)

    @property
    def api_host(self) -> str:
        return self.get("api.host", "0.0.0.0")

    @property
    def api_timeout(self) -> int:
        return self.get("api.timeout", 30)

    @property
    def api_base_url(self) -> str:
        return self.get("frontend.api_base_url", "http://localhost:8000")

    def reload(self) -> None:
        """重新加载配置"""
        self._config = {}
        self.load()


# 全局单例
config = Config()