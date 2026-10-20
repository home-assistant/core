"""Component to interface with an alarm control panel."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    ATTR_CODE_FORMAT,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CHANGED_BY,
    ATTR_CODE_ARM_REQUIRED,
    CONF_DEFAULT_CODE,
    DATA_COMPONENT,
    DOMAIN,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelEntityStateAttribute,
    AlarmControlPanelState,
    CodeFormat,
)
from .entity import AlarmControlPanelEntity, AlarmControlPanelEntityDescription
from .services import async_setup_services

_LOGGER: Final = logging.getLogger(__name__)

ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA: Final = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE: Final = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL: Final = timedelta(seconds=30)

__all__ = [
    "ATTR_CHANGED_BY",
    "ATTR_CODE",
    "ATTR_CODE_ARM_REQUIRED",
    "ATTR_CODE_FORMAT",
    "CONF_DEFAULT_CODE",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_ALARM_ARM_AWAY",
    "SERVICE_ALARM_ARM_CUSTOM_BYPASS",
    "SERVICE_ALARM_ARM_HOME",
    "SERVICE_ALARM_ARM_NIGHT",
    "SERVICE_ALARM_ARM_VACATION",
    "SERVICE_ALARM_DISARM",
    "SERVICE_ALARM_TRIGGER",
    "AlarmControlPanelEntity",
    "AlarmControlPanelEntityDescription",
    "AlarmControlPanelEntityFeature",
    "AlarmControlPanelEntityStateAttribute",
    "AlarmControlPanelState",
    "CodeFormat",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the alarm control panel component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[AlarmControlPanelEntity](
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
