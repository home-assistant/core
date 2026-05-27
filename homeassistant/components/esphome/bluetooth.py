"""Bluetooth support for esphome."""

from functools import partial
import logging
from typing import TYPE_CHECKING

from aioesphomeapi import (
    APIClient,
    APIVersion,
    BluetoothProxyFeature,
    BluetoothScannerMode,
    BluetoothScannerStateResponse,
    DeviceInfo,
)
from bleak_esphome import connect_scanner

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    async_register_scanner,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback

from .const import CONF_BLUETOOTH_SCANNING_MODE, DEFAULT_BLUETOOTH_SCANNING_MODE, DOMAIN
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData

if TYPE_CHECKING:
    from bleak_esphome.backend.scanner import ESPHomeScanner

_LOGGER = logging.getLogger(__name__)
_VALID_SCANNING_MODES = {mode.value for mode in BluetoothScanningMode}


@hass_callback
def _async_unload(unload_callbacks: list[CALLBACK_TYPE]) -> None:
    """Cancel all the callbacks on unload."""
    for callback in unload_callbacks:
        callback()


@hass_callback
def async_connect_scanner(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    entry_data: RuntimeEntryData,
    cli: APIClient,
    device_info: DeviceInfo,
    device_id: str,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    client_data = connect_scanner(cli, device_info, entry_data.available)
    entry_data.bluetooth_device = client_data.bluetooth_device
    client_data.disconnect_callbacks = entry_data.disconnect_callbacks
    scanner = client_data.scanner
    if TYPE_CHECKING:
        assert scanner is not None
    api_version = cli.api_version or APIVersion()
    feature_flags = device_info.bluetooth_proxy_feature_flags_compat(api_version)
    state_and_mode = bool(feature_flags & BluetoothProxyFeature.FEATURE_STATE_AND_MODE)
    # Pin mode before async_register_scanner so habluetooth spawns the AUTO worker.
    deferred_migration: CALLBACK_TYPE | None = None
    if state_and_mode:
        deferred_migration = _async_apply_scanning_mode(hass, entry, scanner, cli)
    callbacks: list[CALLBACK_TYPE] = [
        async_register_scanner(
            hass,
            scanner,
            source_domain=DOMAIN,
            source_model=device_info.model,
            source_config_entry_id=entry_data.entry_id,
            source_device_id=device_id,
        ),
        scanner.async_setup(),
    ]
    if deferred_migration is not None:
        callbacks.append(deferred_migration)
    return partial(_async_unload, callbacks)


@hass_callback
def _async_apply_scanning_mode(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    scanner: ESPHomeScanner,
    cli: APIClient,
) -> CALLBACK_TYPE | None:
    """Apply saved scanning mode synchronously; migrate from configured_mode later."""
    saved = entry.options.get(CONF_BLUETOOTH_SCANNING_MODE)
    if saved is not None and saved not in _VALID_SCANNING_MODES:
        _LOGGER.warning("%s: unknown scanning mode %r", entry.title, saved)
        saved = None
    initial_value = saved if saved is not None else DEFAULT_BLUETOOTH_SCANNING_MODE
    scanner.async_set_scanning_mode(BluetoothScanningMode(initial_value))
    if saved is not None:
        return None

    unsub_holder: list[CALLBACK_TYPE] = []

    @hass_callback
    def _migrate(state: BluetoothScannerStateResponse) -> None:
        # proto3 unset enums decode to None; wait for a real value.
        if (configured_pb := state.configured_mode) is None:
            return
        if unsub_holder:
            unsub_holder.pop()()
        if configured_pb is BluetoothScannerMode.PASSIVE:
            new_mode = BluetoothScanningMode.PASSIVE
        else:
            new_mode = BluetoothScanningMode(DEFAULT_BLUETOOTH_SCANNING_MODE)
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_BLUETOOTH_SCANNING_MODE: new_mode.value,
            },
        )
        # AUTO -> AUTO is already pinned; only re-apply on a downgrade.
        if new_mode is not BluetoothScanningMode(DEFAULT_BLUETOOTH_SCANNING_MODE):
            scanner.async_set_scanning_mode(new_mode)

    unsub_holder.append(cli.subscribe_bluetooth_scanner_state(_migrate))

    @hass_callback
    def _unsubscribe() -> None:
        if unsub_holder:
            unsub_holder.pop()()

    return _unsubscribe
