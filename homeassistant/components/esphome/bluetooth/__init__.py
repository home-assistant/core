"""Bluetooth support for esphome."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial
import logging

from aioesphomeapi import APIClient, BluetoothProxyFeature

from homeassistant.components.bluetooth import (
    HaBluetoothConnector,
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback

from ..entry_data import RuntimeEntryData
from .client import ESPHomeClient
from .scanner import ESPHomeScanner

_LOGGER = logging.getLogger(__name__)


@hass_callback
def _async_can_connect_factory(
    entry_data: RuntimeEntryData, source: str
) -> Callable[[], bool]:
    """Create a can_connect function for a specific RuntimeEntryData instance."""

    @hass_callback
    def _async_can_connect() -> bool:
        """Check if a given source can make another connection."""
        can_connect = bool(entry_data.available and entry_data.ble_connections_free)
        _LOGGER.debug(
            (
                "%s [%s]: Checking can connect, available=%s, ble_connections_free=%s"
                " result=%s"
            ),
            entry_data.name,
            source,
            entry_data.available,
            entry_data.ble_connections_free,
            can_connect,
        )
        return can_connect

    return _async_can_connect


async def async_connect_scanner(
    hass: HomeAssistant,
    entry: ConfigEntry,
    cli: APIClient,
    entry_data: RuntimeEntryData,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    assert entry.unique_id is not None
    source = str(entry.unique_id)
    new_info_callback = async_get_advertisement_callback(hass)
    assert entry_data.device_info is not None
    feature_flags = entry_data.device_info.bluetooth_proxy_feature_flags_compat(
        entry_data.api_version
    )
    connectable = bool(feature_flags & BluetoothProxyFeature.ACTIVE_CONNECTIONS)
    _LOGGER.debug(
        "%s [%s]: Connecting scanner feature_flags=%s, connectable=%s",
        entry.title,
        source,
        feature_flags,
        connectable,
    )
    connector = HaBluetoothConnector(
        # MyPy doesn't like partials, but this is correct
        # https://github.com/python/mypy/issues/1484
        client=partial(ESPHomeClient, config_entry=entry),  # type: ignore[arg-type]
        source=source,
        can_connect=_async_can_connect_factory(entry_data, source),
    )
    scanner = ESPHomeScanner(
        hass, source, entry.title, new_info_callback, connector, connectable
    )
    if connectable:
        # If its connectable be sure not to register the scanner
        # until we know the connection is fully setup since otherwise
        # there is a race condition where the connection can fail
        await cli.subscribe_bluetooth_connections_free(
            entry_data.async_update_ble_connection_limits
        )
    unload_callbacks = [
        async_register_scanner(hass, scanner, connectable),
        scanner.async_setup(),
    ]
    if feature_flags & BluetoothProxyFeature.RAW_ADVERTISEMENTS:
        await cli.subscribe_bluetooth_le_raw_advertisements(
            scanner.async_on_raw_advertisements
        )
    else:
        await cli.subscribe_bluetooth_le_advertisements(scanner.async_on_advertisement)

    @hass_callback
    def _async_unload() -> None:
        for callback in unload_callbacks:
            callback()

    return _async_unload
