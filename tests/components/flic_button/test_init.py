"""Test the Flic Button integration init."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BleakError

from homeassistant.components.flic_button.const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
    FLIC_BUTTON_EVENT,
    DeviceType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import (
    FLIC2_ADDRESS,
    TEST_BATTERY_LEVEL,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    TWIST_ADDRESS,
    TWIST_SERIAL,
    create_flic2_service_info,
    create_mock_flic_client,
)

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup entry."""
    mock_config_entry.add_to_hass(hass)

    service_info = create_flic2_service_info()
    mock_client = create_mock_flic_client()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is mock_client
    mock_client.start.assert_called_once()


async def test_setup_entry_device_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry when device is not available (BLE device not found)."""
    mock_config_entry.add_to_hass(hass)

    mock_client = create_mock_flic_client()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,  # Device not available
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should still load (device will connect when available)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # start() should not be called when no BLE device available
    mock_client.start.assert_not_called()


async def test_setup_entry_initial_connection_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry when initial connection fails (retries later)."""
    mock_config_entry.add_to_hass(hass)

    service_info = create_flic2_service_info()
    mock_client = create_mock_flic_client()
    mock_client.start = AsyncMock(side_effect=BleakError("Connection failed"))

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should still load (will retry when device is available)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading entry."""
    mock_config_entry.add_to_hass(hass)

    service_info = create_flic2_service_info()
    mock_client = create_mock_flic_client()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Unload the entry
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.stop.assert_called_once()


async def test_setup_entry_with_twist_device(
    hass: HomeAssistant,
) -> None:
    """Test setup entry with Twist device type."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Twist ({TWIST_SERIAL})",
        unique_id=TWIST_ADDRESS,
        data={
            CONF_ADDRESS: TWIST_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: TWIST_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.TWIST.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    mock_client = create_mock_flic_client(
        address=TWIST_ADDRESS,
        serial_number=TWIST_SERIAL,
        is_twist=True,
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_bus_event_fired_on_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test bus event is fired when button event callback is triggered."""
    mock_config_entry.add_to_hass(hass)

    mock_client = create_mock_flic_client()
    button_callbacks: list = []

    def capture_button_cb(cb):
        button_callbacks.append(cb)
        return lambda: None

    mock_client.register_button_event_callback = MagicMock(
        side_effect=capture_button_cb
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Capture bus events
    events: list[dict[str, Any]] = []

    hass.bus.async_listen(FLIC_BUTTON_EVENT, lambda e: events.append(e.data))

    # Entity callback is registered first (during platform setup),
    # bus callback from __init__.py is second
    assert len(button_callbacks) >= 2
    bus_cb = button_callbacks[1]
    bus_cb("click", {"extra": "data"})
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0]["event_type"] == "click"
    assert events[0]["address"] == FLIC2_ADDRESS
    assert events[0]["extra"] == "data"
    assert "device_id" in events[0]


async def test_bus_event_fired_on_rotate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test bus event is fired when rotate event callback is triggered."""
    mock_config_entry.add_to_hass(hass)

    mock_client = create_mock_flic_client()
    rotate_callbacks: list = []

    def capture_rotate_cb(cb):
        rotate_callbacks.append(cb)
        return lambda: None

    mock_client.register_rotate_event_callback = MagicMock(
        side_effect=capture_rotate_cb
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    events: list[dict[str, Any]] = []
    hass.bus.async_listen(FLIC_BUTTON_EVENT, lambda e: events.append(e.data))

    # Bus callback from __init__.py is the last registered
    # (Flic2 has no entity rotate callback, so only 1 rotate callback total)
    bus_cb = rotate_callbacks[-1]
    bus_cb("twist_increment", {"value": 3})
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0]["event_type"] == "twist_increment"
    assert events[0]["address"] == FLIC2_ADDRESS


async def test_state_change_updates_firmware_version(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state change callback updates firmware version in device registry."""
    mock_config_entry.add_to_hass(hass)

    mock_client = create_mock_flic_client()
    state_callbacks: list = []

    def capture_state_cb(cb):
        state_callbacks.append(cb)
        return lambda: None

    mock_client.register_state_callback = MagicMock(side_effect=capture_state_cb)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Simulate state change with firmware version
    mock_client.state.connected = True
    mock_client.state.firmware_version = 42
    mock_client.state.device_name = None

    # The first state callback is from __init__.py (_handle_state_change)
    init_state_cb = state_callbacks[0]
    init_state_cb(mock_client.state)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None
    assert device.sw_version == "42"


async def test_bluetooth_callback_sets_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Bluetooth callback updates BLE device on the client."""
    mock_config_entry.add_to_hass(hass)

    mock_client = create_mock_flic_client()
    bt_callback = None

    def capture_bt_register(hass_inner, callback, matcher, mode):
        nonlocal bt_callback
        bt_callback = callback
        return lambda: None

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            side_effect=capture_bt_register,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert bt_callback is not None

    # Simulate Bluetooth advertisement
    service_info = create_flic2_service_info()
    bt_callback(service_info, MagicMock())

    mock_client.set_ble_device.assert_called_once_with(service_info.device)
