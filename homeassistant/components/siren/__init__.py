"""Component to interface with various sirens/chimes."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_AVAILABLE_TONES,
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DATA_COMPONENT,
    DOMAIN,
    SirenEntityCapabilityAttribute,
    SirenEntityFeature,
)
from .entity import SirenEntity, SirenEntityDescription
from .services import (
    TURN_ON_SCHEMA,
    SirenTurnOnServiceParameters,
    async_setup_services,
    process_turn_on_params,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)


__all__ = [
    "ATTR_AVAILABLE_TONES",
    "ATTR_DURATION",
    "ATTR_TONE",
    "ATTR_VOLUME_LEVEL",
    "DOMAIN",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_TOGGLE",
    "SERVICE_TURN_OFF",
    "SERVICE_TURN_ON",
    "STATE_OFF",
    "STATE_ON",
    "TURN_ON_SCHEMA",
    "SirenEntity",
    "SirenEntityCapabilityAttribute",
    "SirenEntityDescription",
    "SirenEntityFeature",
    "SirenTurnOnServiceParameters",
    "process_turn_on_params",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up siren devices."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[SirenEntity](
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
