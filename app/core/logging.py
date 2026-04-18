"""Structured JSON logging configuration.

Call `configure_logging()` once at application startup. After that, use
the standard `logging` module anywhere in the codebase — output will be
JSON-formatted when `APP_ENV != "dev"` and pretty-printed otherwise.
"""

import logging
import sys

from app.core.config import settings

_LOG_FORMAT_DEV = "%(levelname)-8s %(name)s  %(message)s"
_LOG_FORMAT_JSON = (
    '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}'
)


def configure_logging() -> None:
    """Configure root logger based on environment."""
    is_dev = settings.app_env == "dev"
    fmt = _LOG_FORMAT_DEV if is_dev else _LOG_FORMAT_JSON

    logging.basicConfig(
        level=logging.DEBUG if is_dev else logging.INFO,
        format=fmt,
        stream=sys.stdout,
        force=True,
    )

    # Silence noisy third-party loggers in non-dev environments
    if not is_dev:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
