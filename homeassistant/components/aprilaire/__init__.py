"""The Aprilaire integration."""

from __future__ import annotations

import logging

from pyaprilaire.const import Attribute

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac

from .coordinator import AprilaireConfigEntry, AprilaireCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.HUMIDIFIER,
    Platform.SELECT,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: AprilaireConfigEntry) -> bool:
    """Set up a config entry for Aprilaire."""

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    coordinator = AprilaireCoordinator(hass, entry.unique_id, host, port)
    await coordinator.start_listen()

    async def ready_callback(ready: bool) -> None:
        if ready:
            mac_address = format_mac(coordinator.data[Attribute.MAC_ADDRESS])

            if mac_address != entry.unique_id:
                raise ConfigEntryAuthFailed("Invalid MAC address")

            entry.runtime_data = coordinator
            entry.async_on_unload(coordinator.stop_listen)

            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

            async def _async_close(_: Event) -> None:
                coordinator.stop_listen()

            entry.async_on_unload(
                hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close)
            )
        else:
            _LOGGER.error("Failed to wait for ready")

            coordinator.stop_listen()

            raise ConfigEntryNotReady

    await coordinator.wait_for_ready(ready_callback)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AprilaireConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
