"""Provides functionality to interact with humidifier devices."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MODE,
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
    ATTR_ACTION,
    ATTR_AVAILABLE_MODES,
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_TARGET_HUMIDITY_STEP,
    DATA_COMPONENT,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    MODE_AUTO,
    MODE_AWAY,
    MODE_BABY,
    MODE_BOOST,
    MODE_COMFORT,
    MODE_ECO,
    MODE_HOME,
    MODE_NORMAL,
    MODE_SLEEP,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntityCapabilityAttribute,
    HumidifierEntityFeature,
    HumidifierEntityStateAttribute,
    HumidifierService,
    HumidifierServiceArgument,
)
from .entity import HumidifierEntity, HumidifierEntityDescription
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)


# DEVICE_CLASSES below is deprecated as of 2021.12
# use the HumidifierDeviceClass enum instead.
DEVICE_CLASSES = [cls.value for cls in HumidifierDeviceClass]

__all__ = [
    "ATTR_ACTION",
    "ATTR_AVAILABLE_MODES",
    "ATTR_CURRENT_HUMIDITY",
    "ATTR_HUMIDITY",
    "ATTR_MAX_HUMIDITY",
    "ATTR_MIN_HUMIDITY",
    "ATTR_MODE",
    "ATTR_TARGET_HUMIDITY_STEP",
    "DEFAULT_MAX_HUMIDITY",
    "DEFAULT_MIN_HUMIDITY",
    "DEVICE_CLASSES_SCHEMA",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "MODE_AUTO",
    "MODE_AWAY",
    "MODE_BABY",
    "MODE_BOOST",
    "MODE_COMFORT",
    "MODE_ECO",
    "MODE_HOME",
    "MODE_NORMAL",
    "MODE_SLEEP",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_SET_HUMIDITY",
    "SERVICE_SET_MODE",
    "SERVICE_TOGGLE",
    "SERVICE_TURN_OFF",
    "SERVICE_TURN_ON",
    "STATE_OFF",
    "STATE_ON",
    "HumidifierAction",
    "HumidifierDeviceClass",
    "HumidifierEntity",
    "HumidifierEntityCapabilityAttribute",
    "HumidifierEntityDescription",
    "HumidifierEntityFeature",
    "HumidifierEntityStateAttribute",
    "HumidifierService",
    "HumidifierServiceArgument",
]

# mypy: disallow-any-generics


def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the humidifier is on based on the statemachine.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up humidifier devices."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[HumidifierEntity](
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
