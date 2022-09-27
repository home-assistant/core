"""Bluetooth support for esphome."""
from __future__ import annotations

from aioesphomeapi import APIClient
from awesomeversion import AwesomeVersion

from homeassistant.components.bluetooth import (
    HaBluetoothConnector,
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    CALLBACK_TYPE,
    HomeAssistant,
    async_get_hass,
    callback as hass_callback,
)

from ..domain_data import DomainData
from ..entry_data import RuntimeEntryData
from .client import ESPHomeClient
from .scanner import ESPHomeScanner

CONNECTABLE_MIN_VERSION = AwesomeVersion("2022.10.0")


@hass_callback
def async_can_connect(source: str) -> bool:
    """Check if a given source can make another connection."""
    domain_data = DomainData.get(async_get_hass())
    entry = domain_data.get_by_unique_id(source)
    # TODO: return False if we run out of connections.
    return domain_data.get_entry_data(entry).available


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
    connectable = (
        entry_data.device_info
        and AwesomeVersion(entry_data.device_info.esphome_version)
        >= CONNECTABLE_MIN_VERSION
    )
    connectable = True  # TODO: remove this line
    connector = HaBluetoothConnector(
        client=ESPHomeClient,
        source=source,
        can_connect=lambda: async_can_connect(source),
    )
    scanner = ESPHomeScanner(hass, source, new_info_callback, connector, connectable)
    unload_callbacks = [
        async_register_scanner(hass, scanner, connectable),
        scanner.async_setup(),
    ]
    await cli.subscribe_bluetooth_le_advertisements(scanner.async_on_advertisement)

    @hass_callback
    def _async_unload() -> None:
        for callback in unload_callbacks:
            callback()

    return _async_unload
