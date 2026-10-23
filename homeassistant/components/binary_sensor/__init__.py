"""Component to interface with binary sensors."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DEVICE_CLASSES_SCHEMA, DOMAIN, BinarySensorDeviceClass
from .entity import BinarySensorEntity, BinarySensorEntityDescription

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[BinarySensorEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


DEVICE_CLASSES = [cls.value for cls in BinarySensorDeviceClass]

__all__ = [
    "DEVICE_CLASSES",
    "DEVICE_CLASSES_SCHEMA",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "STATE_OFF",
    "STATE_ON",
    "BinarySensorDeviceClass",
    "BinarySensorEntity",
    "BinarySensorEntityDescription",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for binary sensors."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[BinarySensorEntity](
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
