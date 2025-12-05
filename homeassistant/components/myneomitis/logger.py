"""Logging utilities for the MyNeomitis integration."""

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def log_ws_update(entity_name: str, state: dict[str, Any]) -> None:
    """Log a WebSocket update for a device."""
    _LOGGER.debug(
        "WebSocket update for %s: temp=%.1f°C, mode=%s",
        entity_name,
        state.get("currentTemp", -1),
        state.get("targetMode", "N/A"),
    )
