"""Services for the Shelly integration."""
from __future__ import annotations

from homeassistant.const import ATTR_AREA_ID, ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import BLOCK, DATA_CONFIG_ENTRY, DOMAIN, RPC, SERVICE_OTA_UPDATE
from .utils import get_device_entry_gen


async def async_services_setup(hass: HomeAssistant) -> None:
    """Set up services."""

    async def async_service_ota_update(call: ServiceCall) -> None:
        """Trigger OTA update."""
        if not (call.data.get(ATTR_DEVICE_ID) or call.data.get(ATTR_AREA_ID)):
            raise HomeAssistantError("No target selected for OTA update")

        beta_channel = bool(call.data.get("beta"))

        entry_ids = await async_extract_config_entry_ids(hass, call)
        for entry_id in entry_ids:
            entry = hass.config_entries.async_get_entry(entry_id)
            if not (entry and entry.domain == DOMAIN):
                continue

            if active_entry := hass.data[DOMAIN][DATA_CONFIG_ENTRY].get(entry.entry_id):
                if get_device_entry_gen(entry) == 2:
                    wrapper = active_entry.get(RPC)
                else:
                    wrapper = active_entry.get(BLOCK)
                await wrapper.async_trigger_ota_update(beta=beta_channel)

    hass.services.async_register(DOMAIN, SERVICE_OTA_UPDATE, async_service_ota_update)
