"""Private BLE Device integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv, discovery_flow

from .const import DOMAIN

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tracking of a private bluetooth device from a config entry."""

    async def service_register_irk(call: ServiceCall) -> None:
        """Trigger Private BLE Device to add an IRK."""
        if _irk := call.data.get("irk", False):
            discovery_flow.async_create_flow(
                hass,
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data={"irk": _irk},
            )

    # Register action for creating new Private_BLE_Devices
    hass.services.async_register(
        DOMAIN,
        "register_irk",
        service_register_irk,
        vol.Schema(
            {
                vol.Required("irk"): cv.string,
            }
        ),
        supports_response=SupportsResponse.NONE,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entities for a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
