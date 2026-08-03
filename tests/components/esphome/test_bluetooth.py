"""Test the ESPHome bluetooth integration."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

from aioesphomeapi import (
    BluetoothProxyFeature,
    BluetoothScannerMode,
    BluetoothScannerState,
    BluetoothScannerStateResponse,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.esphome.const import CONF_BLUETOOTH_SCANNING_MODE
from homeassistant.core import HomeAssistant, callback as hass_callback
from homeassistant.helpers import device_registry as dr

from .conftest import MockBluetoothEntryType, MockESPHomeDevice

_PROXY_WITH_STATE_AND_MODE = (
    BluetoothProxyFeature.PASSIVE_SCAN
    | BluetoothProxyFeature.ACTIVE_CONNECTIONS
    | BluetoothProxyFeature.RAW_ADVERTISEMENTS
    | BluetoothProxyFeature.FEATURE_STATE_AND_MODE
)


async def test_bluetooth_connect_with_raw_adv(
    hass: HomeAssistant, mock_bluetooth_entry_with_raw_adv: MockESPHomeDevice
) -> None:
    """Test bluetooth connect with raw advertisements."""
    scanner = bluetooth.async_scanner_by_source(hass, "AA:BB:CC:DD:EE:FC")
    assert scanner is not None
    assert scanner.connectable is True
    assert scanner.scanning is True
    assert scanner.connector.can_connect() is False  # no connection slots
    await mock_bluetooth_entry_with_raw_adv.mock_disconnect(True)
    await hass.async_block_till_done()

    scanner = bluetooth.async_scanner_by_source(hass, "AA:BB:CC:DD:EE:FC")
    assert scanner is None
    await mock_bluetooth_entry_with_raw_adv.mock_connect()
    await hass.async_block_till_done()
    scanner = bluetooth.async_scanner_by_source(hass, "AA:BB:CC:DD:EE:FC")
    assert scanner.scanning is True


async def test_bluetooth_connect_with_legacy_adv(
    hass: HomeAssistant, mock_bluetooth_entry_with_legacy_adv: MockESPHomeDevice
) -> None:
    """Test bluetooth connect with legacy advertisements."""
    scanner = bluetooth.async_scanner_by_source(hass, "AA:BB:CC:DD:EE:FC")
    assert scanner is not None
    assert scanner.connectable is True
    assert scanner.scanning is True
    assert scanner.connector.can_connect() is False  # no connection slots
    await mock_bluetooth_entry_with_legacy_adv.mock_disconnect(True)
    await hass.async_block_till_done()

    scanner = bluetooth.async_scanner_by_source(hass, "AA:BB:CC:DD:EE:FC")
    assert scanner is None
    await mock_bluetooth_entry_with_legacy_adv.mock_connect()
    await hass.async_block_till_done()
    scanner = bluetooth.async_scanner_by_source(hass, "AA:BB:CC:DD:EE:FC")
    assert scanner.scanning is True


async def test_bluetooth_device_linked_via_device(
    hass: HomeAssistant,
    mock_bluetooth_entry_with_raw_adv: MockESPHomeDevice,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the Bluetooth device is linked to the ESPHome device."""
    scanner = bluetooth.async_scanner_by_source(hass, "AA:BB:CC:DD:EE:FC")
    assert scanner.connectable is True
    entry = hass.config_entries.async_entry_for_domain_unique_id(
        "bluetooth", "AA:BB:CC:DD:EE:FC"
    )
    assert entry is not None
    esp_device = device_registry.async_get_device(
        connections={
            (
                dr.CONNECTION_NETWORK_MAC,
                mock_bluetooth_entry_with_raw_adv.device_info.mac_address,
            )
        }
    )
    assert esp_device is not None
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_BLUETOOTH, "AA:BB:CC:DD:EE:FC")}
    )
    assert device is not None
    assert device.via_device_id == esp_device.id


async def test_bluetooth_cleanup_on_remove_entry(
    hass: HomeAssistant, mock_bluetooth_entry_with_raw_adv: MockESPHomeDevice
) -> None:
    """Test bluetooth is cleaned up on entry removal."""
    scanner = bluetooth.async_scanner_by_source(hass, "AA:BB:CC:DD:EE:FC")
    assert scanner.connectable is True
    await hass.config_entries.async_unload(
        mock_bluetooth_entry_with_raw_adv.entry.entry_id
    )

    with patch("homeassistant.components.esphome.async_remove_scanner") as remove_mock:
        await hass.config_entries.async_remove(
            mock_bluetooth_entry_with_raw_adv.entry.entry_id
        )
        await hass.async_block_till_done()

    remove_mock.assert_called_once_with(hass, scanner.source)


async def test_scanning_mode_saved_option_applied(
    hass: HomeAssistant,
    mock_bluetooth_entry: MockBluetoothEntryType,
) -> None:
    """A saved CONF_BLUETOOTH_SCANNING_MODE is applied immediately to the proxy."""
    device = await mock_bluetooth_entry(
        bluetooth_proxy_feature_flags=_PROXY_WITH_STATE_AND_MODE
    )
    hass.config_entries.async_update_entry(
        device.entry,
        options={**device.entry.options, CONF_BLUETOOTH_SCANNING_MODE: "passive"},
    )
    set_mode_mock = MagicMock()
    device.client.bluetooth_scanner_set_mode = set_mode_mock
    await hass.config_entries.async_reload(device.entry.entry_id)
    await hass.async_block_till_done()

    set_mode_mock.assert_any_call(BluetoothScannerMode.PASSIVE)


async def test_scanning_mode_invalid_option_falls_back_to_default(
    hass: HomeAssistant,
    mock_bluetooth_entry: MockBluetoothEntryType,
) -> None:
    """A malformed saved value falls back to the AUTO default instead of raising."""
    device = await mock_bluetooth_entry(
        bluetooth_proxy_feature_flags=_PROXY_WITH_STATE_AND_MODE
    )
    hass.config_entries.async_update_entry(
        device.entry,
        options={**device.entry.options, CONF_BLUETOOTH_SCANNING_MODE: "bogus"},
    )
    set_mode_mock = MagicMock()
    device.client.bluetooth_scanner_set_mode = set_mode_mock
    await hass.config_entries.async_reload(device.entry.entry_id)
    await hass.async_block_till_done()

    # AUTO maps to PASSIVE on the firmware.
    set_mode_mock.assert_any_call(BluetoothScannerMode.PASSIVE)


async def test_scanning_mode_migration_passive_is_honored(
    hass: HomeAssistant,
    mock_bluetooth_entry: MockBluetoothEntryType,
) -> None:
    """Proxy configured PASSIVE in YAML is honored on first state update."""
    set_mode_mock = MagicMock()
    state_subscriptions: list[Callable[[BluetoothScannerStateResponse], None]] = []

    def _subscribe(
        callback: Callable[[BluetoothScannerStateResponse], None],
    ) -> Callable[[], None]:
        state_subscriptions.append(callback)
        return lambda: state_subscriptions.remove(callback)

    device = await mock_bluetooth_entry(
        bluetooth_proxy_feature_flags=_PROXY_WITH_STATE_AND_MODE
    )
    device.client.bluetooth_scanner_set_mode = set_mode_mock
    device.client.subscribe_bluetooth_scanner_state = _subscribe
    await hass.config_entries.async_reload(device.entry.entry_id)
    await hass.async_block_till_done()

    assert state_subscriptions
    for callback in state_subscriptions[:]:
        callback(
            BluetoothScannerStateResponse(
                state=BluetoothScannerState.RUNNING,
                mode=BluetoothScannerMode.PASSIVE,
                configured_mode=BluetoothScannerMode.PASSIVE,
            )
        )
    await hass.async_block_till_done()

    assert device.entry.options[CONF_BLUETOOTH_SCANNING_MODE] == "passive"
    set_mode_mock.assert_any_call(BluetoothScannerMode.PASSIVE)


async def test_scanning_mode_migration_waits_for_known_configured_mode(
    hass: HomeAssistant,
    mock_bluetooth_entry: MockBluetoothEntryType,
) -> None:
    """An initial state with configured_mode=None must not commit a migration."""
    state_subscriptions: list[Callable[[BluetoothScannerStateResponse], None]] = []
    set_mode_mock = MagicMock()

    def _subscribe(
        callback: Callable[[BluetoothScannerStateResponse], None],
    ) -> Callable[[], None]:
        state_subscriptions.append(callback)
        return lambda: state_subscriptions.remove(callback)

    device = await mock_bluetooth_entry(
        bluetooth_proxy_feature_flags=_PROXY_WITH_STATE_AND_MODE
    )
    device.client.bluetooth_scanner_set_mode = set_mode_mock
    device.client.subscribe_bluetooth_scanner_state = _subscribe
    await hass.config_entries.async_reload(device.entry.entry_id)
    await hass.async_block_till_done()

    assert state_subscriptions
    for callback in state_subscriptions[:]:
        callback(
            BluetoothScannerStateResponse(
                state=BluetoothScannerState.RUNNING,
                mode=None,
                configured_mode=None,
            )
        )
    await hass.async_block_till_done()

    assert CONF_BLUETOOTH_SCANNING_MODE not in device.entry.options
    # A second response with a real configured_mode commits the migration.
    for callback in state_subscriptions[:]:
        callback(
            BluetoothScannerStateResponse(
                state=BluetoothScannerState.RUNNING,
                mode=BluetoothScannerMode.PASSIVE,
                configured_mode=BluetoothScannerMode.PASSIVE,
            )
        )
    await hass.async_block_till_done()
    assert device.entry.options[CONF_BLUETOOTH_SCANNING_MODE] == "passive"


async def test_scanning_mode_pending_subscription_unsubscribes_on_unload(
    hass: HomeAssistant,
    mock_bluetooth_entry: MockBluetoothEntryType,
) -> None:
    """Unloading before the first state update cancels the migration subscription."""
    state_subscriptions: list[Callable[[BluetoothScannerStateResponse], None]] = []
    unsub_calls: list[Callable[[BluetoothScannerStateResponse], None]] = []

    def _subscribe(
        callback: Callable[[BluetoothScannerStateResponse], None],
    ) -> Callable[[], None]:
        state_subscriptions.append(callback)

        def _unsub() -> None:
            unsub_calls.append(callback)
            state_subscriptions.remove(callback)

        return _unsub

    device = await mock_bluetooth_entry(
        bluetooth_proxy_feature_flags=_PROXY_WITH_STATE_AND_MODE
    )
    device.client.subscribe_bluetooth_scanner_state = _subscribe
    await hass.config_entries.async_reload(device.entry.entry_id)
    await hass.async_block_till_done()
    # The migration subscription is pending; tear the entry down without
    # firing a state update so _unsubscribe in bluetooth.py runs the
    # cancellation arm.
    assert state_subscriptions
    await hass.config_entries.async_unload(device.entry.entry_id)
    await hass.async_block_till_done()
    assert unsub_calls


async def test_scanning_mode_migration_active_becomes_auto(
    hass: HomeAssistant,
    mock_bluetooth_entry: MockBluetoothEntryType,
) -> None:
    """Proxy configured ACTIVE migrates to AUTO on first state update."""
    set_mode_mock = MagicMock()
    state_subscriptions: list[Callable[[BluetoothScannerStateResponse], None]] = []

    def _subscribe(
        callback: Callable[[BluetoothScannerStateResponse], None],
    ) -> Callable[[], None]:
        state_subscriptions.append(callback)
        return lambda: state_subscriptions.remove(callback)

    device = await mock_bluetooth_entry(
        bluetooth_proxy_feature_flags=_PROXY_WITH_STATE_AND_MODE
    )
    device.client.bluetooth_scanner_set_mode = set_mode_mock
    device.client.subscribe_bluetooth_scanner_state = _subscribe
    await hass.config_entries.async_reload(device.entry.entry_id)
    await hass.async_block_till_done()

    # AUTO was applied at setup before async_register_scanner so habluetooth's
    # scheduler spawns a worker; AUTO maps to PASSIVE on the firmware.
    assert set_mode_mock.call_args_list == [((BluetoothScannerMode.PASSIVE,), {})]
    set_mode_mock.reset_mock()
    assert state_subscriptions
    for callback in state_subscriptions[:]:
        callback(
            BluetoothScannerStateResponse(
                state=BluetoothScannerState.RUNNING,
                mode=BluetoothScannerMode.ACTIVE,
                configured_mode=BluetoothScannerMode.ACTIVE,
            )
        )
    await hass.async_block_till_done()

    assert device.entry.options[CONF_BLUETOOTH_SCANNING_MODE] == "auto"
    # AUTO -> AUTO does not re-send a firmware command.
    set_mode_mock.assert_not_called()


async def test_scanning_mode_default_pinned_before_register(
    hass: HomeAssistant,
    mock_bluetooth_entry: MockBluetoothEntryType,
) -> None:
    """The default AUTO is applied immediately so the AUTO worker spawns at register."""
    set_mode_mock = MagicMock()
    requested_at_register: list[BluetoothScanningMode | None] = []
    real_register = bluetooth.async_register_scanner

    @hass_callback
    def _spy_register(*args: Any, **kwargs: Any) -> Callable[[], None]:
        requested_at_register.append(args[1].requested_mode)
        return real_register(*args, **kwargs)

    device = await mock_bluetooth_entry(
        bluetooth_proxy_feature_flags=_PROXY_WITH_STATE_AND_MODE
    )
    device.client.bluetooth_scanner_set_mode = set_mode_mock
    with patch(
        "homeassistant.components.esphome.bluetooth.async_register_scanner",
        _spy_register,
    ):
        await hass.config_entries.async_reload(device.entry.entry_id)
        await hass.async_block_till_done()

    # AUTO -> PASSIVE is sent before async_register_scanner, so the
    # habluetooth auto-mode worker is spawned at registration time.
    set_mode_mock.assert_called_once_with(BluetoothScannerMode.PASSIVE)
    assert requested_at_register == [BluetoothScanningMode.AUTO]
