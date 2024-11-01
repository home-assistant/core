"""Helpers for amcrest component."""

from __future__ import annotations

import logging

from homeassistant.helpers.typing import UndefinedType

from .const import DOMAIN


def service_signal(service: str, *args: str) -> str:
    """Encode signal."""
    return "_".join([DOMAIN, service, *args])


def log_update_error(
    logger: logging.Logger,
    action: str,
    name: str | UndefinedType | None,
    entity_type: str,
    error: Exception,
    level: int = logging.ERROR,
) -> None:
    """Log an update error."""
    logger.log(
        level,
        "Could not %s %s %s due to error: %s",
        action,
        name,
        entity_type,
        error.__class__.__name__,
    )
