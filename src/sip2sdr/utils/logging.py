"""Structured logging setup for SIP2SDR.

Call ``configure_logging()`` once at application startup.  All modules
should use ``logging.getLogger(__name__)`` to obtain their logger.
"""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with a structured format.

    Args:
        level: Log level string, e.g. "DEBUG", "INFO", "WARNING".
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.addHandler(handler)
