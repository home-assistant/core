"""Support for Valve devices."""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (  # noqa: F401
    DOMAIN,
    ValveDeviceClass,
    ValveEntityFeature,
    ValveState,
)
from .entity import (  # noqa: F401
    ATTR_CURRENT_POSITION,
    ATTR_IS_CLOSED,
    ValveEntity,
    ValveEntityDescription,
)

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[ValveEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=15)


DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.Coerce(ValveDeviceClass))


ATTR_POSITION = "position"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for valves."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[ValveEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_OPEN_VALVE, None, "async_handle_open_valve", [ValveEntityFeature.OPEN]
    )

    component.async_register_entity_service(
        SERVICE_CLOSE_VALVE,
        None,
        "async_handle_close_valve",
        [ValveEntityFeature.CLOSE],
    )

    component.async_register_entity_service(
        SERVICE_SET_VALVE_POSITION,
        {
            vol.Required(ATTR_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_valve_position",
        [ValveEntityFeature.SET_POSITION],
    )

    component.async_register_entity_service(
        SERVICE_STOP_VALVE, None, "async_stop_valve", [ValveEntityFeature.STOP]
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
