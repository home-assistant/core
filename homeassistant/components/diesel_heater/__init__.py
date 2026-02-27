"""The Diesel Heater integration.

Supports Vevor, BYD, HeaterCC, Sunster and other Chinese diesel heaters via BLE.
"""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import VevorHeaterCoordinator

type DieselHeaterConfigEntry = ConfigEntry[VevorHeaterCoordinator]

_LOGGER = logging.getLogger(__name__)

# Service constants
SERVICE_SEND_COMMAND = "send_command"
ATTR_COMMAND = "command"
ATTR_ARGUMENT = "argument"
ATTR_DEVICE_ID = "device_id"

SERVICE_SEND_COMMAND_SCHEMA = vol.Schema({
    vol.Optional(ATTR_DEVICE_ID): cv.string,
    vol.Required(ATTR_COMMAND): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    vol.Required(ATTR_ARGUMENT): vol.All(vol.Coerce(int), vol.Range(min=-128, max=127)),
})

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Diesel Heater integration."""

    async def async_send_command(call: ServiceCall) -> None:
        """Handle send_command service call for debugging."""
        command = call.data[ATTR_COMMAND]
        argument = call.data[ATTR_ARGUMENT]
        device_id = call.data.get(ATTR_DEVICE_ID)

        _LOGGER.debug(
            "Service %s.%s called: command=%d, argument=%d, device_id=%s",
            DOMAIN, SERVICE_SEND_COMMAND, command, argument, device_id
        )

        # Find target heaters
        target_coords: list[VevorHeaterCoordinator] = []
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            coord = getattr(config_entry, "runtime_data", None)
            if not isinstance(coord, VevorHeaterCoordinator):
                continue
            if device_id:
                # Normalize both for comparison (strip colons/hyphens)
                norm_device = device_id.upper().replace(":", "").replace("-", "")
                norm_addr = coord.address.upper().replace(":", "")
                if norm_device in norm_addr or norm_addr.endswith(norm_device):
                    target_coords.append(coord)
            else:
                target_coords.append(coord)

        if not target_coords:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_heater_found",
                translation_placeholders={"device_id": device_id or "all"},
            )

        for coord in target_coords:
            try:
                await coord.async_send_raw_command(command, argument)
            except Exception as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_failed",
                    translation_placeholders={
                        "address": coord.address,
                        "error": str(err),
                    },
                ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        async_send_command,
        schema=SERVICE_SEND_COMMAND_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: DieselHeaterConfigEntry) -> bool:
    """Set up Diesel Heater from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    _LOGGER.debug("Setting up Diesel Heater with address: %s", address)

    # Get BLE device from Home Assistant's bluetooth integration
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), connectable=True
    )

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Diesel Heater with address {address}"
        )

    # Create coordinator
    coordinator = VevorHeaterCoordinator(hass, ble_device, entry)

    # Load persistent fuel data
    await coordinator.async_load_data()

    # Initial data fetch with timeout
    try:
        await asyncio.wait_for(
            coordinator.async_config_entry_first_refresh(),
            timeout=30.0,
        )
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Initial connection to Diesel Heater at {address} "
            "timed out after 30 seconds"
        ) from err

    # Store coordinator on the config entry
    entry.runtime_data = coordinator

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DieselHeaterConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: VevorHeaterCoordinator = entry.runtime_data
        # Save fuel data before shutdown
        await coordinator.async_save_data()
        await coordinator.async_shutdown()

    return unload_ok
