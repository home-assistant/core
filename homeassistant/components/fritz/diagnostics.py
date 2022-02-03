"""Diagnostics support for AVM FRITZ!Box."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .common import AvmWrapper
from .const import DOMAIN

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    diag_data = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": {
            "model": avm_wrapper.model,
            "current_firmware": avm_wrapper.current_firmware,
            "latest_firmware": avm_wrapper.latest_firmware,
            "update_available": avm_wrapper.update_available,
            "is_router": avm_wrapper.device_is_router,
            "mesh_role": avm_wrapper.mesh_role,
            "last_update success": avm_wrapper.last_update_success,
            "last_exception": avm_wrapper.last_exception,
        },
    }

    return diag_data
