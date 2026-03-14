"""Specialized Turbo BLE integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PIN
from .coordinator import SpecializedTurboCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type SpecializedTurboConfigEntry = ConfigEntry[SpecializedTurboCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SpecializedTurboConfigEntry
) -> bool:
    """Set up Specialized Turbo from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    pin: int | None = entry.data.get(CONF_PIN)

    coordinator = SpecializedTurboCoordinator(
        hass,
        _LOGGER,
        address=address,
        pin=pin,
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SpecializedTurboConfigEntry
) -> bool:
    """Unload a Specialized Turbo config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
