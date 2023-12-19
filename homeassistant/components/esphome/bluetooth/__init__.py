"""Bluetooth support for esphome."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from functools import partial
import logging
from typing import TYPE_CHECKING, Any

from aioesphomeapi import APIClient, BluetoothProxyFeature, DeviceInfo
from bleak_esphome.backend.cache import ESPHomeBluetoothCache
from bleak_esphome.backend.client import ESPHomeClient, ESPHomeClientData
from bleak_esphome.backend.device import ESPHomeBluetoothDevice
from bleak_esphome.backend.scanner import ESPHomeScanner

from homeassistant.components.bluetooth import (
    HaBluetoothConnector,
    async_register_scanner,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback

from ..entry_data import RuntimeEntryData

_LOGGER = logging.getLogger(__name__)


def _async_can_connect(bluetooth_device: ESPHomeBluetoothDevice, source: str) -> bool:
    """Check if a given source can make another connection."""
    can_connect = bool(
        bluetooth_device.available and bluetooth_device.ble_connections_free
    )
    _LOGGER.debug(
        (
            "%s [%s]: Checking can connect, available=%s, ble_connections_free=%s"
            " result=%s"
        ),
        bluetooth_device.name,
        source,
        bluetooth_device.available,
        bluetooth_device.ble_connections_free,
        can_connect,
    )
    return can_connect


@hass_callback
def _async_unload(unload_callbacks: list[CALLBACK_TYPE]) -> None:
    """Cancel all the callbacks on unload."""
    for callback in unload_callbacks:
        callback()


async def async_connect_scanner(
    hass: HomeAssistant,
    entry_data: RuntimeEntryData,
    cli: APIClient,
    device_info: DeviceInfo,
    cache: ESPHomeBluetoothCache,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    source = device_info.mac_address
    name = device_info.name
    if TYPE_CHECKING:
        assert cli.api_version is not None
    feature_flags = device_info.bluetooth_proxy_feature_flags_compat(cli.api_version)
    connectable = bool(feature_flags & BluetoothProxyFeature.ACTIVE_CONNECTIONS)
    bluetooth_device = ESPHomeBluetoothDevice(
        name, device_info.mac_address, available=entry_data.available
    )
    entry_data.bluetooth_device = bluetooth_device
    _LOGGER.debug(
        "%s [%s]: Connecting scanner feature_flags=%s, connectable=%s",
        name,
        source,
        feature_flags,
        connectable,
    )
    client_data = ESPHomeClientData(
        bluetooth_device=bluetooth_device,
        cache=cache,
        client=cli,
        device_info=device_info,
        api_version=cli.api_version,
        title=name,
        scanner=None,
        disconnect_callbacks=entry_data.disconnect_callbacks,
    )
    connector = HaBluetoothConnector(
        # MyPy doesn't like partials, but this is correct
        # https://github.com/python/mypy/issues/1484
        client=partial(ESPHomeClient, client_data=client_data),  # type: ignore[arg-type]
        source=source,
        can_connect=partial(_async_can_connect, bluetooth_device, source),
    )
    scanner = ESPHomeScanner(source, name, connector, connectable)
    client_data.scanner = scanner
    coros: list[Coroutine[Any, Any, CALLBACK_TYPE]] = []
    # These calls all return a callback that can be used to unsubscribe
    # but we never unsubscribe so we don't care about the return value

    if connectable:
        # If its connectable be sure not to register the scanner
        # until we know the connection is fully setup since otherwise
        # there is a race condition where the connection can fail
        coros.append(
            cli.subscribe_bluetooth_connections_free(
                bluetooth_device.async_update_ble_connection_limits
            )
        )

    if feature_flags & BluetoothProxyFeature.RAW_ADVERTISEMENTS:
        coros.append(
            cli.subscribe_bluetooth_le_raw_advertisements(
                scanner.async_on_raw_advertisements
            )
        )
    else:
        coros.append(
            cli.subscribe_bluetooth_le_advertisements(scanner.async_on_advertisement)
        )

    await asyncio.gather(*coros)
    return partial(
        _async_unload,
        [
            async_register_scanner(hass, scanner, connectable),
            scanner.async_setup(),
        ],
    )
