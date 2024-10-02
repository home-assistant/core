"""The ezbeq Profile Loader integration."""

from __future__ import annotations

import logging

from pyezbeq.ezbeq import EzbeqClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import EzBEQCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EzBEQConfigEntry = ConfigEntry[EzBEQCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EzBEQConfigEntry) -> bool:
    """Set up ezbeq Profile Loader from a config entry."""
    _LOGGER.debug("Setting up ezbeq from a config entry")
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    client = EzbeqClient(host=host, port=port, logger=_LOGGER)
    coordinator = EzBEQCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # create a device for the server
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (
                DOMAIN,
                f"{coordinator.config_entry.entry_id}_{coordinator.config_entry.data[CONF_HOST]}",
            )
        },
        name="EzBEQ",
        manufacturer="EzBEQ",
        sw_version=coordinator.client.version,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Finished setting up ezbeq from a config entry")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EzBEQConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading ezbeq config entry")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.client.client.aclose()
    return unload_ok
