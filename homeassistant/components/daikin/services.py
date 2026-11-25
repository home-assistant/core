"""Services for the Daikin integration."""

from enum import StrEnum

import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DAIKIN_DEMAND_CONTROL_MODES, DOMAIN, MODE_MANUAL
from .coordinator import DaikinConfigEntry
from .demand_control import async_update_demand_control


class DaikinService(StrEnum):
    """Store keys for Daikin services."""

    SET_DEMAND_CONTROL = "set_demand_control"


class DaikinServiceArgument(StrEnum):
    """Store keys for Daikin service arguments."""

    EN_DEMAND = "en_demand"
    MAX_POW = "max_pow"
    MODE = "mode"


SET_DEMAND_CONTROL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Required(DaikinServiceArgument.EN_DEMAND): bool,
        probatio.Optional(DaikinServiceArgument.MAX_POW, default=100): probatio.All(
            probatio.Coerce(int), probatio.Range(min=40, max=100)
        ),
        probatio.Optional(DaikinServiceArgument.MODE, default=MODE_MANUAL): probatio.In(
            DAIKIN_DEMAND_CONTROL_MODES
        ),
    }
)


async def _extract_config_entry(call: ServiceCall) -> DaikinConfigEntry:
    """Extract the Daikin config entry targeted by a service call."""
    target_entry_ids = await async_extract_config_entry_ids(call)
    target_entries: list[DaikinConfigEntry] = [
        loaded_entry
        for loaded_entry in call.hass.config_entries.async_loaded_entries(DOMAIN)
        if loaded_entry.entry_id in target_entry_ids
    ]
    if not target_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="demand_control_invalid_device",
        )
    return target_entries[0]


async def async_set_demand_control(call: ServiceCall) -> None:
    """Set the demand control maximum power of the unit."""
    entry = await _extract_config_entry(call)
    await async_update_demand_control(
        entry.runtime_data,
        enabled=call.data[DaikinServiceArgument.EN_DEMAND],
        max_power=call.data[DaikinServiceArgument.MAX_POW],
        mode=call.data[DaikinServiceArgument.MODE],
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Daikin services."""
    hass.services.async_register(
        DOMAIN,
        DaikinService.SET_DEMAND_CONTROL,
        async_set_demand_control,
        SET_DEMAND_CONTROL_SCHEMA,
    )
