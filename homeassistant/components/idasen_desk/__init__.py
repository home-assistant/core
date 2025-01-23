"""The IKEA Idasen Desk integration."""

from __future__ import annotations

import logging

from bleak.exc import BleakError
from idasen_ha.errors import AuthFailedError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import IdasenDeskCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.COVER, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type IdasenDeskConfigEntry = ConfigEntry[IdasenDeskCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IdasenDeskConfigEntry) -> bool:
    """Set up IKEA Idasen from a config entry."""
    address: str = entry.data[CONF_ADDRESS].upper()

    coordinator = IdasenDeskCoordinator(hass, entry.title, address)
    entry.runtime_data = coordinator

    try:
        if not await coordinator.async_connect():
            raise ConfigEntryNotReady(f"Unable to connect to desk {address}")  # noqa: TRY301
    except (AuthFailedError, TimeoutError, BleakError, Exception) as ex:
        raise ConfigEntryNotReady(f"Unable to connect to desk {address}") from ex

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    @callback
    def _async_bluetooth_callback(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a Bluetooth callback to ensure that a new BLEDevice is fetched."""
        _LOGGER.debug("Bluetooth callback triggered")
        hass.async_create_task(coordinator.async_connect_if_expected())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_bluetooth_callback,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await coordinator.async_disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: IdasenDeskConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IdasenDeskConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.async_disconnect()
        bluetooth.async_rediscover_address(hass, coordinator.address)

    return unload_ok
