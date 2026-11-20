"""Services for the Ness Alarm integration."""

from enum import StrEnum
from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

if TYPE_CHECKING:
    from . import NessAlarmConfigEntry


class NessAlarmService(StrEnum):
    """Store keys for Ness Alarm services."""

    AUX = "aux"
    PANIC = "panic"


class NessAlarmServiceArgument(StrEnum):
    """Store keys for Ness Alarm service arguments."""

    OUTPUT_ID = "output_id"
    STATE = "state"
    CODE = "code"


SERVICE_SCHEMA_PANIC = probatio.Schema(
    {probatio.Required(NessAlarmServiceArgument.CODE): cv.string}
)
SERVICE_SCHEMA_AUX = probatio.Schema(
    {
        probatio.Required(NessAlarmServiceArgument.OUTPUT_ID): cv.positive_int,
        probatio.Optional(NessAlarmServiceArgument.STATE, default=True): cv.boolean,
    }
)


async def _handle_panic(call: ServiceCall) -> None:
    """Handle panic service call."""
    entry: NessAlarmConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    await entry.runtime_data.panic(call.data[NessAlarmServiceArgument.CODE])


async def _handle_aux(call: ServiceCall) -> None:
    """Handle aux service call."""
    entry: NessAlarmConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, None
    )
    await entry.runtime_data.aux(
        call.data[NessAlarmServiceArgument.OUTPUT_ID],
        call.data[NessAlarmServiceArgument.STATE],
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Ness Alarm services."""

    hass.services.async_register(
        DOMAIN, NessAlarmService.PANIC, _handle_panic, schema=SERVICE_SCHEMA_PANIC
    )
    hass.services.async_register(
        DOMAIN, NessAlarmService.AUX, _handle_aux, schema=SERVICE_SCHEMA_AUX
    )
