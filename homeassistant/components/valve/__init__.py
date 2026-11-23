"""Support for Valve devices."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_STOP_VALVE,
    SERVICE_TOGGLE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_POSITION,
    DATA_COMPONENT,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    ValveDeviceClass,
    ValveEntityFeature,
    ValveEntityStateAttribute,
    ValveService,
    ValveServiceArgument,
    ValveState,
)
from .entity import (
    ATTR_CURRENT_POSITION,
    ATTR_IS_CLOSED,
    ValveEntity,
    ValveEntityDescription,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=15)

__all__ = [
    "ATTR_CURRENT_POSITION",
    "ATTR_IS_CLOSED",
    "ATTR_POSITION",
    "DEVICE_CLASSES_SCHEMA",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_CLOSE_VALVE",
    "SERVICE_OPEN_VALVE",
    "SERVICE_SET_VALVE_POSITION",
    "SERVICE_STOP_VALVE",
    "SERVICE_TOGGLE",
    "STATE_CLOSED",
    "STATE_CLOSING",
    "STATE_OPEN",
    "STATE_OPENING",
    "ValveDeviceClass",
    "ValveEntity",
    "ValveEntityDescription",
    "ValveEntityFeature",
    "ValveEntityStateAttribute",
    "ValveService",
    "ValveServiceArgument",
    "ValveState",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for valves."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[ValveEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)
