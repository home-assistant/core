"""The RYSE integration."""

from functools import partial
import logging
from typing import TYPE_CHECKING

from bleak import BleakError
from bleak.backends.device import BLEDevice
from ryseble.device import RyseAuthenticationFailed, RyseBLEDevice

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .helpers import async_best_local_scanner_device, async_release_connection

_LOGGER = logging.getLogger(__name__)

type RyseConfigEntry = ConfigEntry[RyseBLEDevice]

PLATFORMS = [Platform.COVER]


def _async_local_ble_device(
    hass: HomeAssistant, address: str, *, prefer: BLEDevice | None = None
) -> BLEDevice | None:
    """Return the BLEDevice from the best local adapter, ignoring Bluetooth proxies."""
    scanner_device = async_best_local_scanner_device(hass, address, prefer=prefer)
    return scanner_device.ble_device if scanner_device else None


async def async_setup_entry(hass: HomeAssistant, entry: RyseConfigEntry) -> None:
    """Set up RYSE."""
    address = entry.unique_id
    if TYPE_CHECKING:
        assert address is not None

    ble_device = _async_local_ble_device(hass, address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find RYSE device with address {address} on a local "
            "Bluetooth adapter"
        )

    device = RyseBLEDevice(ble_device)
    connect_error = f"Could not connect to RYSE device with address {address}"
    paired = False
    try:
        paired = await device.pair()
        if not paired:
            # False is not a confirmed bond rejection.
            raise ConfigEntryNotReady(connect_error)
    except RyseAuthenticationFailed as err:
        raise ConfigEntryAuthFailed(connect_error) from err
    except (TimeoutError, OSError, EOFError, BleakError) as err:
        raise ConfigEntryNotReady(connect_error) from err
    finally:
        if not paired:
            await async_release_connection(device)

    entry.runtime_data = device
    # Wrap disconnect so a teardown error cannot replace ConfigEntryNotReady
    # when Home Assistant runs on_unload after a failed setup.
    entry.async_on_unload(partial(async_release_connection, device))

    missing_local_route = False
    current_ble_device = ble_device

    @callback
    def _async_update_ble_device(
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Refresh the BLEDevice from a local adapter, ignoring Bluetooth proxies.

        Local adapters set ``service_info.source`` to the adapter MAC, not
        ``SOURCE_LOCAL``. Resolve via scanners that currently see the address.
        Stay on the adapter that holds the BlueZ bond when several locals see it.
        """
        nonlocal missing_local_route, current_ble_device
        ble_device = _async_local_ble_device(
            hass, service_info.address, prefer=current_ble_device
        )
        if ble_device is None:
            if not missing_local_route:
                _LOGGER.info(
                    "No local Bluetooth adapter currently sees %s; "
                    "commands require a local adapter, not a proxy",
                    service_info.address,
                )
                missing_local_route = True
            return
        if missing_local_route:
            _LOGGER.info(
                "%s is visible on a local Bluetooth adapter again",
                service_info.address,
            )
            missing_local_route = False
        current_ble_device = ble_device
        device.set_ble_device(ble_device)

    entry.async_on_unload(
        async_register_callback(
            hass,
            _async_update_ble_device,
            BluetoothCallbackMatcher(address=address, connectable=True),
            BluetoothScanningMode.PASSIVE,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: RyseConfigEntry) -> None:
    """Unload a RYSE config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
