"""Services for the BSB-Lan integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bsblan import BSBLANError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from . import BSBLanConfigEntry


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for BSB-Lan integration."""

    async def async_sync_time(call: ServiceCall) -> None:
        """Handle the sync_time service call."""
        entry_id: str = call.data[ATTR_CONFIG_ENTRY_ID]
        entry = hass.config_entries.async_get_entry(entry_id)

        if not entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
            )

        if entry.state != ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
            )

        # Type cast to BSBLanConfigEntry to access runtime_data
        bsblan_entry: BSBLanConfigEntry = entry
        client = bsblan_entry.runtime_data.client

        try:
            # Get current device time
            device_time = await client.time()
            current_time = dt_util.now()
            current_time_str = current_time.strftime("%d.%m.%Y %H:%M:%S")

            # Only sync if device time differs from HA time
            if device_time.time.value != current_time_str:
                await client.set_time(current_time_str)
        except BSBLANError as err:
            raise HomeAssistantError(
                f"Failed to sync time for {entry.title}: {err}"
            ) from err

    hass.services.async_register(
        DOMAIN,
        "sync_time",
        async_sync_time,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            }
        ),
    )
