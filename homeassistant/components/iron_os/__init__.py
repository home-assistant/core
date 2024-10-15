"""The IronOS integration."""

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
from .coordinator import IronOSCoordinator

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR]

type IronOSConfigEntry = ConfigEntry[IronOSCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: IronOSConfigEntry) -> bool:
    """Set up IronOS from a config entry."""
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

    device = Pynecil(ble_device)

    coordinator = IronOSCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IronOSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
