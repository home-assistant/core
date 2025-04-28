"""Constants for the Kitchen Sink integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.util.hass_dict import HassKey

DOMAIN = "kitchen_sink"
DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
