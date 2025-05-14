"""Constants for the Homeassistant integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from homeassistant import core as ha
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .exposed_entities import ExposedEntities

DOMAIN = ha.DOMAIN

DATA_EXPOSED_ENTITIES: HassKey[ExposedEntities] = HassKey(f"{DOMAIN}.exposed_entites")
DATA_STOP_HANDLER = f"{DOMAIN}.stop_handler"

SERVICE_HOMEASSISTANT_STOP: Final = "stop"
SERVICE_HOMEASSISTANT_RESTART: Final = "restart"
