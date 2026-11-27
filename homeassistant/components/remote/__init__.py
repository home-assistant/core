"""Support to interface with universal remote control devices."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_COMMAND,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ACTIVITY,
    ATTR_ACTIVITY_LIST,
    ATTR_ALTERNATIVE,
    ATTR_COMMAND_TYPE,
    ATTR_CURRENT_ACTIVITY,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    ATTR_TIMEOUT,
    DATA_COMPONENT,
    DEFAULT_DELAY_SECS,
    DEFAULT_HOLD_SECS,
    DEFAULT_NUM_REPEATS,
    DOMAIN,
    SERVICE_DELETE_COMMAND,
    SERVICE_LEARN_COMMAND,
    SERVICE_SEND_COMMAND,
    SERVICE_SYNC,
    RemoteEntityFeature,
    RemoteEntityStateAttribute,
    RemoteService,
    RemoteServiceArgument,
)
from .entity import RemoteEntity, RemoteEntityDescription
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

__all__ = [
    "ATTR_ACTIVITY",
    "ATTR_ACTIVITY_LIST",
    "ATTR_ALTERNATIVE",
    "ATTR_COMMAND",
    "ATTR_COMMAND_TYPE",
    "ATTR_CURRENT_ACTIVITY",
    "ATTR_DELAY_SECS",
    "ATTR_DEVICE",
    "ATTR_HOLD_SECS",
    "ATTR_NUM_REPEATS",
    "ATTR_TIMEOUT",
    "DEFAULT_DELAY_SECS",
    "DEFAULT_HOLD_SECS",
    "DEFAULT_NUM_REPEATS",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_DELETE_COMMAND",
    "SERVICE_LEARN_COMMAND",
    "SERVICE_SEND_COMMAND",
    "SERVICE_SYNC",
    "SERVICE_TOGGLE",
    "SERVICE_TURN_OFF",
    "SERVICE_TURN_ON",
    "STATE_OFF",
    "STATE_ON",
    "RemoteEntity",
    "RemoteEntityDescription",
    "RemoteEntityFeature",
    "RemoteEntityStateAttribute",
    "RemoteService",
    "RemoteServiceArgument",
]


def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the remote is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for remotes."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[RemoteEntity](
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
