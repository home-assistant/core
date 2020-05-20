"""Vaillant service."""
import logging

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.util.dt import parse_date

from .const import (
    ATTR_DURATION,
    ATTR_END_DATE,
    ATTR_QUICK_MODE,
    ATTR_START_DATE,
    ATTR_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)

QUICK_MODES_LIST = [
    "QM_HOTWATER_BOOST",
    "QM_VENTILATION_BOOST",
    "QM_PARTY",
    "QM_ONE_DAY_AWAY",
    "QM_SYSTEM_OFF",
    "QM_ONE_DAY_AT_HOME",
]

SERVICE_REMOVE_QUICK_MODE = "remove_quick_mode"
SERVICE_REMOVE_HOLIDAY_MODE = "remove_holiday_mode"
SERVICE_SET_QUICK_MODE = "set_quick_mode"
SERVICE_SET_HOLIDAY_MODE = "set_holiday_mode"
SERVICE_SET_QUICK_VETO = "set_quick_veto"
SERVICE_REMOVE_QUICK_VETO = "remove_quick_veto"
SERVICE_REQUEST_HVAC_UPDATE = "request_hvac_update"

SERVICE_REMOVE_QUICK_MODE_SCHEMA = vol.Schema({})
SERVICE_REMOVE_HOLIDAY_MODE_SCHEMA = vol.Schema({})
SERVICE_REMOVE_QUICK_VETO_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): vol.All(vol.Coerce(str))}
)
SERVICE_SET_QUICK_MODE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_QUICK_MODE): vol.All(vol.Coerce(str), vol.In(QUICK_MODES_LIST))}
)
SERVICE_SET_HOLIDAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_START_DATE): vol.All(vol.Coerce(str)),
        vol.Required(ATTR_END_DATE): vol.All(vol.Coerce(str)),
        vol.Required(ATTR_TEMPERATURE): vol.All(
            vol.Coerce(float), vol.Clamp(min=5, max=30)
        ),
    }
)
SERVICE_SET_QUICK_VETO_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): vol.All(vol.Coerce(str)),
        vol.Required(ATTR_TEMPERATURE): vol.All(
            vol.Coerce(float), vol.Clamp(min=5, max=30)
        ),
        vol.Required(ATTR_DURATION): vol.All(
            vol.Coerce(int), vol.Clamp(min=30, max=1440)
        ),
    }
)
SERVICE_REQUEST_HVAC_UPDATE_SCHEMA = vol.Schema({})

SERVICES = {
    SERVICE_REMOVE_QUICK_MODE: {
        "method": SERVICE_REMOVE_QUICK_MODE,
        "schema": SERVICE_REMOVE_QUICK_MODE_SCHEMA,
    },
    SERVICE_REMOVE_HOLIDAY_MODE: {
        "method": SERVICE_REMOVE_HOLIDAY_MODE,
        "schema": SERVICE_REMOVE_HOLIDAY_MODE_SCHEMA,
    },
    SERVICE_REMOVE_QUICK_VETO: {
        "method": SERVICE_REMOVE_QUICK_VETO,
        "schema": SERVICE_REMOVE_QUICK_VETO_SCHEMA,
    },
    SERVICE_SET_QUICK_MODE: {
        "method": SERVICE_SET_QUICK_MODE,
        "schema": SERVICE_SET_QUICK_MODE_SCHEMA,
    },
    SERVICE_SET_HOLIDAY_MODE: {
        "method": SERVICE_SET_HOLIDAY_MODE,
        "schema": SERVICE_SET_HOLIDAY_MODE_SCHEMA,
    },
    SERVICE_SET_QUICK_VETO: {
        "method": SERVICE_SET_QUICK_VETO,
        "schema": SERVICE_SET_QUICK_VETO_SCHEMA,
    },
    SERVICE_REQUEST_HVAC_UPDATE: {
        "method": SERVICE_REQUEST_HVAC_UPDATE,
        "schema": SERVICE_REQUEST_HVAC_UPDATE_SCHEMA,
    },
}


class VaillantServiceHandler:
    """Service implementation."""

    def __init__(self, hub, hass) -> None:
        """Init."""
        self._hub = hub
        self._hass = hass

    async def remove_quick_mode(self, call):
        """Remove quick mode. It has impact on all components."""
        await self._hub.remove_quick_mode()

    async def set_holiday_mode(self, call):
        """Set holiday mode."""
        start_str = call.data.get(ATTR_START_DATE, None)
        end_str = call.data.get(ATTR_END_DATE, None)
        temp = call.data.get(ATTR_TEMPERATURE)
        start = parse_date(start_str.split("T")[0])
        end = parse_date(end_str.split("T")[0])
        if end is None or start is None:
            raise ValueError(f"dates are incorrect {start_str} {end_str}")
        await self._hub.set_holiday_mode(start, end, temp)

    async def remove_holiday_mode(self, call):
        """Remove holiday mode."""
        await self._hub.remove_holiday_mode()

    async def set_quick_mode(self, call):
        """Set quick mode, it may impact the whole system."""
        quick_mode = call.data.get(ATTR_QUICK_MODE, None)
        await self._hub.set_quick_mode(quick_mode)

    async def set_quick_veto(self, call):
        """Set quick veto (and remove the existing one) for a given entity."""
        temp = call.data.get(ATTR_TEMPERATURE, None)
        duration = call.data.get(ATTR_DURATION, None)

        entity_id = call.data.get(ATTR_ENTITY_ID, None)
        entity = self._hub.get_entity(entity_id)

        if entity is not None:
            await self._hub.set_quick_veto(entity, temp, duration)
        else:
            _LOGGER.debug("Not entity found for id %s", entity_id)

    async def remove_quick_veto(self, call):
        """Remove quick veto (if any) for a given entity."""
        entity_id = call.data.get(ATTR_ENTITY_ID, None)
        entity = self._hub.get_entity(entity_id)

        if entity is not None:
            await self._hub.remove_quick_veto(entity)
        else:
            _LOGGER.debug("Not entity found for id %s", entity_id)

    async def request_hvac_update(self, call):
        """Ask vaillant API to get data from your installation."""
        await self._hub.request_hvac_update()
