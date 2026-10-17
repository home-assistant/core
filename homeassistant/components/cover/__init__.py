"""Support for Cover devices."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import deprecated_function
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .condition import make_cover_is_closed_condition, make_cover_is_open_condition
from .const import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_IS_CLOSED,
    ATTR_POSITION,
    ATTR_SPEED,
    ATTR_TILT_POSITION,
    DATA_COMPONENT,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    INTENT_CLOSE_COVER,
    INTENT_OPEN_COVER,
    CoverDeviceClass,
    CoverEntityCapabilityAttribute,
    CoverEntityFeature,
    CoverEntityStateAttribute,
    CoverState,
)
from .entity import CoverEntity, CoverEntityDescription
from .services import async_setup_services
from .trigger import make_cover_closed_trigger, make_cover_opened_trigger

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=15)


DEVICE_CLASSES = [cls.value for cls in CoverDeviceClass]

# mypy: disallow-any-generics


__all__ = [
    "ATTR_CURRENT_POSITION",
    "ATTR_CURRENT_TILT_POSITION",
    "ATTR_IS_CLOSED",
    "ATTR_POSITION",
    "ATTR_SPEED",
    "ATTR_TILT_POSITION",
    "DEVICE_CLASSES",
    "DEVICE_CLASSES_SCHEMA",
    "DOMAIN",
    "INTENT_CLOSE_COVER",
    "INTENT_OPEN_COVER",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_CLOSE_COVER",
    "SERVICE_CLOSE_COVER_TILT",
    "SERVICE_OPEN_COVER",
    "SERVICE_OPEN_COVER_TILT",
    "SERVICE_SET_COVER_POSITION",
    "SERVICE_SET_COVER_TILT_POSITION",
    "SERVICE_STOP_COVER",
    "SERVICE_STOP_COVER_TILT",
    "SERVICE_TOGGLE",
    "SERVICE_TOGGLE_COVER_TILT",
    "CoverDeviceClass",
    "CoverEntity",
    "CoverEntityCapabilityAttribute",
    "CoverEntityDescription",
    "CoverEntityFeature",
    "CoverEntityStateAttribute",
    "CoverState",
    "make_cover_closed_trigger",
    "make_cover_is_closed_condition",
    "make_cover_is_open_condition",
    "make_cover_opened_trigger",
]


@deprecated_function(
    "hass.states.is_state(entity_id, 'closed')", breaks_in_ha_version="2027.10"
)
def is_closed(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(entity_id, CoverState.CLOSED)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for covers."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[CoverEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
