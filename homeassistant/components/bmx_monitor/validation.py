"""Validate the BM2 protocol over advertisements or an active BLE connection."""

import contextlib
import logging
from typing import Literal

from bleak.exc import BleakError
from bmx_ble import BM2Generation

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_process_advertisements,
)
from homeassistant.core import HomeAssistant

from .device_data import BMxBluetoothDeviceData as DeviceData

_LOGGER = logging.getLogger(__name__)

# BM2 devices can alternate advertisement packet types.
ADDITIONAL_ADVERTISEMENT_TIMEOUT = 10

type ValidationResult = Literal[
    "valid_passive", "valid_active", "not_bm2", "cannot_validate"
]


def advertisement_is_bm2(
    device: DeviceData, discovery_info: BluetoothServiceInfoBleak
) -> bool:
    """Return whether this advertisement proves BM2 identity."""
    device.update(discovery_info)
    return device.bm2_generation is not BM2Generation.UNKNOWN


async def async_validate_device(
    hass: HomeAssistant, discovery_info: BluetoothServiceInfoBleak
) -> ValidationResult:
    """Validate BM2 identity, preserving uncertainty when a connection fails."""
    address = discovery_info.address
    device = DeviceData()

    if advertisement_is_bm2(device, discovery_info):
        _LOGGER.debug(
            "%s validated as BM2 from %s advertisement",
            address,
            device.bm2_generation,
        )
        return "valid_passive"

    def _process_advertisement(service_info: BluetoothServiceInfoBleak) -> bool:
        return advertisement_is_bm2(device, service_info)

    with contextlib.suppress(TimeoutError):
        await async_process_advertisements(
            hass,
            _process_advertisement,
            {"address": address, "connectable": False},
            BluetoothScanningMode.ACTIVE,
            ADDITIONAL_ADVERTISEMENT_TIMEOUT,
        )

    if device.bm2_generation is not BM2Generation.UNKNOWN:
        _LOGGER.debug(
            "%s validated as BM2 after additional advertisement (%s)",
            address,
            device.bm2_generation,
        )
        return "valid_passive"

    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        _LOGGER.debug(
            "%s could not be actively validated: no connectable path", address
        )
        return "cannot_validate"

    try:
        valid = await device.async_validate_active(ble_device)

    except (BleakError, TimeoutError) as ex:
        # A connection failure is not proof that the device is not a BM2.
        _LOGGER.debug("%s could not be actively validated as BM2: %s", address, ex)

        return "cannot_validate"

    else:
        if valid:
            _LOGGER.debug("%s validated using active BM2 GATT protocol", address)
            return "valid_active"

        return "not_bm2"
