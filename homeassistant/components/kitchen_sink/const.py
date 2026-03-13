"""Constants for the Kitchen Sink integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.util.hass_dict import HassKey

DOMAIN = "kitchen_sink"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)
