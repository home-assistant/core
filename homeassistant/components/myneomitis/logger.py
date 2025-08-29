"""Logging utilities for the MyNeomitis integration."""

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def log_api_update(entity_name: str, state: dict[str, Any]) -> None:
    """Log an API update for a device.

    Args:
        entity_name (str): The name of the entity.
        state (Dict[str, Any]): The state dictionary containing device information.

    """
    _LOGGER.info(
        "MyNeomitis : API UPDATE - %s : currentTemp=%.2f°C | overrideTemp=%.1f°C | min=%.1f°C | max=%.1f°C | mode=%s | consumption=%s",
        entity_name,
        state.get("currentTemp", -1),
        state.get("overrideTemp", -1),
        state.get("comfLimitMin", -1),
        state.get("comfLimitMax", -1),
        state.get("targetMode", "N/A"),
        state.get("consumption", -1),
    )


def log_ws_update(entity_name: str, state: dict[str, Any]) -> None:
    """Log a WebSocket update for a device.

    Args:
        entity_name (str): The name of the entity.
        state (Dict[str, Any]): The state dictionary containing device information.

    """
    _LOGGER.info(
        "MyNeomitis : WS UPDATE - %s : currentTemp=%.2f | overrideTemp=%s | targetMode=%s",
        entity_name,
        state.get("currentTemp", -1),
        state.get("overrideTemp", "N/A"),
        state.get("targetMode", "N/A"),
    )


def log_api_update_switch(entity_name: str, state: dict[str, Any]) -> None:
    """Log an API update for a relay.

    Args:
        entity_name (str): The name of the entity.
        state (Dict[str, Any]): The state dictionary containing relay information.

    """
    _LOGGER.info(
        "MyNeomitis : API UPDATE - %s : targetMode=%s | relayMode=%s | systemPower=%s",
        entity_name,
        state.get("targetMode", "N/A"),
        state.get("relayMode", "N/A"),
        state.get("systemPower", "N/A"),
    )


def log_ws_update_switch(entity_name: str, state: dict[str, Any]) -> None:
    """Log a WebSocket update for a relay.

    Args:
        entity_name (str): The name of the entity.
        state (Dict[str, Any]): The state dictionary containing relay information.

    """
    _LOGGER.info(
        "MyNeomitis : WS UPDATE - %s : targetMode=%s | relayMode=%s",
        entity_name,
        state.get("targetMode", "N/A"),
        state.get("relayMode", "N/A"),
    )


def log_ws_update_ufh(entity_name: str, state: dict[str, Any]) -> None:
    """Log a WebSocket update for an underfloor heating system.

    Args:
        entity_name (str): The name of the entity.
        state (Dict[str, Any]): The state dictionary containing underfloor heating information.

    """
    _LOGGER.info(
        "MyNeomitis : WS UPDATE - %s : changeOverUser=%s | changeOverOutput=%s",
        entity_name,
        state.get("changeOverUser", "N/A"),
        state.get("changeOverOutput", "N/A"),
    )
