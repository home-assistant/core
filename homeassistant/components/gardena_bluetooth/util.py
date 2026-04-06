"""Utility functions for Gardena Bluetooth integration."""

import asyncio
from collections.abc import AsyncIterator

from gardena_bluetooth.parse import ManufacturerData, ProductType

from homeassistant.components import bluetooth


async def _async_service_info(
    hass, address
) -> AsyncIterator[bluetooth.BluetoothServiceInfoBleak]:
    queue = asyncio.Queue[bluetooth.BluetoothServiceInfoBleak]()

    def _callback(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        if change != bluetooth.BluetoothChange.ADVERTISEMENT:
            return

        queue.put_nowait(service_info)

    service_info = bluetooth.async_last_service_info(hass, address, True)
    if service_info:
        yield service_info

    cancel = bluetooth.async_register_callback(
        hass,
        _callback,
        {bluetooth.match.ADDRESS: address},
        bluetooth.BluetoothScanningMode.ACTIVE,
    )
    try:
        while True:
            yield await queue.get()
    finally:
        cancel()


async def async_get_product_type(hass, address: str) -> ProductType:
    """Wait for enough packets of manufacturer data to get the product type."""
    data = ManufacturerData()

    async for service_info in _async_service_info(hass, address):
        data.update(service_info.manufacturer_data.get(ManufacturerData.company, b""))
        product_type = ProductType.from_manufacturer_data(data)
        if product_type is not ProductType.UNKNOWN:
            return product_type
    raise AssertionError("Iterator should have been infinite")
