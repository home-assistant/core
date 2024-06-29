"""The Pinecil integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pynecil import Pynecil

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import PinecilCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type PinecilConfigEntry = ConfigEntry[PinecilCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: PinecilConfigEntry) -> bool:
    """Set up Pinecil from a config entry."""
    if TYPE_CHECKING:
        assert entry.unique_id
    ble_device = bluetooth.async_ble_device_from_address(
        hass, entry.unique_id, connectable=True
    )
    if not ble_device:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_device_unavailable_exception",
            translation_placeholders={CONF_NAME: entry.title},
        )

    pinecil = Pynecil(ble_device)

    coordinator = PinecilCoordinator(hass, pinecil)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PinecilConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
