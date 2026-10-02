"""The BM2 battery monitor integration."""

import logging

from sensor_state_data import SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_address_present,
    async_ble_device_from_address,
    async_last_service_info,
    async_process_advertisements,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .device_data import BMxBluetoothDeviceData
from .validation import async_validate_device

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)
SETUP_ADVERTISEMENT_TIMEOUT = 10

type BMxConfigEntry = ConfigEntry[ActiveBluetoothProcessorCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BMxConfigEntry,
) -> bool:
    """Set up BMx BLE device from a config entry."""
    address = config_entry.unique_id
    assert address is not None

    # A configured device may be reachable only through a passive scanner.
    # Check for a recent advertisement before attempting an active connection.
    service_info = (
        async_last_service_info(hass, address, connectable=False)
        if async_address_present(hass, address, connectable=False)
        else None
    )
    if service_info is None:
        try:
            service_info = await async_process_advertisements(
                hass,
                lambda _info: True,
                {"address": address, "connectable": False},
                BluetoothScanningMode.PASSIVE,
                SETUP_ADVERTISEMENT_TIMEOUT,
            )
        except TimeoutError as ex:
            raise ConfigEntryNotReady(
                f"No advertisement received from {address}"
            ) from ex

    validation = await async_validate_device(hass, service_info)
    if validation == "not_bm2":
        raise ConfigEntryError(f"{address} does not respond to the BM2 protocol")
    if validation == "cannot_validate":
        raise ConfigEntryNotReady(f"Cannot currently validate {address} as a BM2")

    device_data = BMxBluetoothDeviceData()
    device_data.entry = config_entry

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak,
        last_poll: float | None,
    ) -> bool:
        """Return whether this advertisement should trigger a scheduled update."""
        # Previously this condition prevented the poll callback from running at
        # all when the BM2 could only be heard by a passive proxy/scanner.  The
        # updated poll callback can now publish cached advertisement telemetry
        # in that situation, so hearing the device is enough to proceed.
        return hass.state is CoreState.running and device_data.poll_needed(
            service_info, last_poll
        )

    async def _async_poll(
        service_info: BluetoothServiceInfoBleak,
    ) -> SensorUpdate:
        """Try to find a connectable path, otherwise use passive fallback."""
        connectable_device = None

        if service_info.connectable:
            connectable_device = service_info.device
        else:
            connectable_device = async_ble_device_from_address(
                hass,
                service_info.device.address,
                connectable=True,
            )

        # async_poll_sensors(None) is intentional.  BMxBluetoothDeviceData will treat
        # "no connectable path" exactly like a failed active connection and use
        # the cached advertisement if the newer telemetry packet was decoded.
        return await device_data.async_poll_sensors(connectable_device)

    coordinator = config_entry.runtime_data = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=device_data.update,
        needs_poll_method=_needs_poll,
        poll_method=_async_poll,
        # Accept advertisements from non-connectable scanners/proxies.  When a
        # connectable path is available it is still preferred for the GATT read.
        connectable=False,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Only start after all platforms have had a chance to subscribe.
    config_entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: BMxConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
