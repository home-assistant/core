"""Component for handling incoming events as a platform."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    ATTR_MULTI_PRESS_COUNT,
    DOMAIN,
    ButtonEventType,
    DoorbellEventType,
    EventDeviceClass,
    EventEntityCapabilityAttribute,
    EventEntityStateAttribute,
)
from .entity import EventEntity, EventEntityDescription

_LOGGER = logging.getLogger(__name__)
DATA_COMPONENT: HassKey[EntityComponent[EventEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


__all__ = [
    "ATTR_EVENT_TYPE",
    "ATTR_EVENT_TYPES",
    "ATTR_MULTI_PRESS_COUNT",
    "DOMAIN",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "ButtonEventType",
    "DoorbellEventType",
    "EventDeviceClass",
    "EventEntity",
    "EventEntityCapabilityAttribute",
    "EventEntityDescription",
    "EventEntityStateAttribute",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Event entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[EventEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
