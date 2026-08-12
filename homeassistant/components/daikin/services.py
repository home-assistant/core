"""Services for the Daikin integration."""

from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import (
    ATTR_EN_DEMAND,
    ATTR_MAX_POW,
    DOMAIN,
    SERVICE_SET_DEMAND_CONTROL,
    SET_DEMAND_CONTROL_SCHEMA,
)
from .coordinator import DaikinConfigEntry


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
    device = entry.runtime_data.device
    if not device.support_demand_control:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="demand_control_unsupported",
        )
    await device.set_demand_control(
        en_demand="on" if call.data[ATTR_EN_DEMAND] else "off",
        max_pow=call.data[ATTR_MAX_POW],
        mode=call.data[ATTR_MODE],
    )
    await entry.runtime_data.async_refresh()


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Daikin services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DEMAND_CONTROL,
        async_set_demand_control,
        SET_DEMAND_CONTROL_SCHEMA,
    )
