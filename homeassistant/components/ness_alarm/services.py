"""Services for the Ness Alarm integration."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import ATTR_CODE, ATTR_STATE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_OUTPUT_ID, DOMAIN, SERVICE_AUX, SERVICE_PANIC

if TYPE_CHECKING:
    from . import NessAlarmConfigEntry

SERVICE_SCHEMA_PANIC = vol.Schema({vol.Required(ATTR_CODE): cv.string})
SERVICE_SCHEMA_AUX = vol.Schema(
    {
        vol.Required(ATTR_OUTPUT_ID): cv.positive_int,
        vol.Optional(ATTR_STATE, default=True): cv.boolean,
    }
)


async def _handle_panic(call: ServiceCall) -> None:
    """Handle panic service call."""
    entry: NessAlarmConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    await entry.runtime_data.panic(call.data[ATTR_CODE])


async def _handle_aux(call: ServiceCall) -> None:
    """Handle aux service call."""
    entry: NessAlarmConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    await entry.runtime_data.aux(call.data[ATTR_OUTPUT_ID], call.data[ATTR_STATE])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Ness Alarm services."""

    hass.services.async_register(
        DOMAIN, SERVICE_PANIC, _handle_panic, schema=SERVICE_SCHEMA_PANIC
    )
    hass.services.async_register(
        DOMAIN, SERVICE_AUX, _handle_aux, schema=SERVICE_SCHEMA_AUX
    )
