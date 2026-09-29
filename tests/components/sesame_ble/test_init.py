"""Tests for the Sesame BLE integration setup and lifecycle."""

import asyncio
import struct
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import UUID

import pytest

from homeassistant.components import sesame_ble
from homeassistant.components.sesame_ble.const import (
    CONF_DEVICE_UUID,
    CONF_SECRET_KEY,
    DOMAIN,
)
from homeassistant.components.sesame_ble.lock import SesameBLELock
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_UUID = UUID("01234567-89ab-cdef-0123-456789abcdef")


@pytest.mark.asyncio
async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of Sesame BLE lock entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_success",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_register_callback",
            return_value=MagicMock(),
        ),
        patch.object(
            sesame_ble.SesameDeviceWrapper,
            "async_connect",
            new_callable=AsyncMock,
        ) as mock_connect,
    ):
        setup_ok = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert setup_ok is True
    mock_connect.assert_awaited_once()
    assert entry.runtime_data is not None
    assert entry.runtime_data.model_name == "SESAME5"
    assert entry.state is ConfigEntryState.LOADED
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, sesame_ble.PLATFORMS
    )
    await entry.runtime_data.async_disconnect()


@pytest.mark.asyncio
async def test_setup_entry_device_not_found(hass: HomeAssistant) -> None:
    """Test setup raises ConfigEntryNotReady when device is not in Bluetooth cache."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_not_found",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


def test_lock_has_entity_name() -> None:
    """Verify that SesameBLELock sets has_entity_name = True."""
    wrapper = MagicMock()
    wrapper.entry.unique_id = "test_entry"
    wrapper.device = MagicMock()
    lock = SesameBLELock(wrapper)
    assert lock.has_entity_name is True


@pytest.mark.asyncio
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test entry unloading disconnects the wrapper."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_unload_entry",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    mock_wrapper = MagicMock()
    mock_wrapper.async_disconnect = AsyncMock()
    entry.runtime_data = mock_wrapper

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ):
        result = await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    mock_wrapper.async_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_unload_suppresses_disconnect_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that disconnecting during unload suppresses unexpected disconnect warning."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_unload_suppression",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    wrapper = sesame_ble.SesameDeviceWrapper(
        hass,
        entry,
        MagicMock(),
        MagicMock(),
        "0123456789abcdef0123456789abcdef",
        "SESAME5",
    )
    wrapper.device.disconnect = AsyncMock()

    await wrapper.async_disconnect()
    wrapper._handle_device_disconnect()

    assert "disconnected unexpectedly" not in caplog.text


@pytest.mark.asyncio
async def test_unexpected_disconnect_logs_warning(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an unexpected disconnect logs a warning."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_unexpected_disc",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    wrapper = sesame_ble.SesameDeviceWrapper(
        hass,
        entry,
        MagicMock(),
        MagicMock(),
        "0123456789abcdef0123456789abcdef",
        "SESAME5",
    )
    wrapper._handle_device_disconnect()

    assert "disconnected unexpectedly" in caplog.text


@pytest.mark.asyncio
async def test_bluetooth_callbacks_and_unavailable_tracking(
    hass: HomeAssistant,
) -> None:
    """Test Bluetooth advertisement and unavailable callbacks trigger listener notifications."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_bt_callbacks",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    adv_callback = None
    unavail_callback = None

    registered_matcher = None
    tracked_address = None

    def mock_register_callback(
        hass: HomeAssistant, cb: Any, matcher: Any, mode: Any
    ) -> MagicMock:
        nonlocal adv_callback, registered_matcher
        adv_callback = cb
        registered_matcher = matcher
        return MagicMock()

    def mock_track_unavail(
        hass: HomeAssistant, cb: Any, address: str, connectable: bool = True
    ) -> MagicMock:
        nonlocal unavail_callback, tracked_address
        unavail_callback = cb
        tracked_address = address
        return MagicMock()

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_register_callback",
            side_effect=mock_register_callback,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_track_unavailable",
            side_effect=mock_track_unavail,
        ),
        patch.object(
            sesame_ble.SesameDeviceWrapper,
            "async_connect",
            new_callable=AsyncMock,
        ),
    ):
        setup_ok = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert setup_ok is True
    assert adv_callback is not None
    assert unavail_callback is not None
    assert registered_matcher is not None
    assert registered_matcher["address"] == mock_ble_device.address
    assert tracked_address == mock_ble_device.address

    listener_called = False

    def listener():
        nonlocal listener_called
        listener_called = True

    entry.runtime_data.register_update_listener(listener)

    # 1. Trigger advertisement callback
    new_device = MagicMock()
    service_info = MagicMock()
    service_info.device = new_device
    listener_called = False
    adv_callback(service_info, None)
    assert listener_called is True
    assert entry.runtime_data.ble_device is new_device

    # 2. Trigger unavailable callback
    listener_called = False
    unavail_callback(service_info)
    assert listener_called is True

    await entry.runtime_data.async_disconnect()


@pytest.mark.asyncio
async def test_bluetooth_advertisement_reconnects_when_disconnected(
    hass: HomeAssistant,
) -> None:
    """Test receiving advertisement triggers reconnect when device is disconnected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_reconnect",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)

    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    adv_callback = None

    def mock_register_callback(
        hass: HomeAssistant,
        cb: Any,
        matcher: Any,
        mode: Any,
    ) -> MagicMock:
        nonlocal adv_callback
        adv_callback = cb
        return MagicMock()

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_register_callback",
            side_effect=mock_register_callback,
        ),
        patch.object(
            sesame_ble.SesameDeviceWrapper,
            "async_connect",
            new_callable=AsyncMock,
        ) as mock_connect,
    ):
        setup_ok = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert setup_ok is True
        assert mock_connect.await_count == 1
        assert adv_callback is not None

        # Simulate device disconnected
        wrapper = entry.runtime_data
        wrapper.device._client = None

        new_device = MagicMock()
        service_info = MagicMock()
        service_info.device = new_device

        adv_callback(service_info, None)
        await hass.async_block_till_done()

        assert mock_connect.await_count == 2
        await wrapper.async_disconnect()


@pytest.mark.asyncio
async def test_bluetooth_advertisement_reconnects_when_connected_but_not_logged_in(
    hass: HomeAssistant,
) -> None:
    """Test receiving advertisement triggers reconnect when device is connected but not logged in."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_reconnect_not_logged_in",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)

    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    adv_callback = None

    def mock_register_callback(
        hass: HomeAssistant,
        cb: Any,
        matcher: Any,
        mode: Any,
    ) -> MagicMock:
        nonlocal adv_callback
        adv_callback = cb
        return MagicMock()

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_register_callback",
            side_effect=mock_register_callback,
        ),
        patch.object(
            sesame_ble.SesameDeviceWrapper,
            "async_connect",
            new_callable=AsyncMock,
        ) as mock_connect,
    ):
        setup_ok = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert setup_ok is True
        assert mock_connect.await_count == 1
        assert adv_callback is not None

        # Simulate device connected but login dropped
        wrapper = entry.runtime_data
        wrapper.device.is_logged_in = False

        with patch.object(
            type(wrapper.device),
            "is_connected",
            new_callable=PropertyMock(return_value=True),
        ):
            new_device = MagicMock()
            service_info = MagicMock()
            service_info.device = new_device

            adv_callback(service_info, None)
            await hass.async_block_till_done()

            assert mock_connect.await_count == 2
        await wrapper.async_disconnect()


@pytest.mark.asyncio
async def test_setup_entry_no_uuid_and_no_adv_retries(hass: HomeAssistant) -> None:
    """Test setup raises ConfigEntryNotReady when device has no UUID and no advertisement."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_no_uuid_no_adv",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
        },
    )
    entry.add_to_hass(hass)
    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.asyncio
async def test_setup_entry_device_mismatch_model(hass: HomeAssistant) -> None:
    """Test setup raises ConfigEntryError when advertisement model does not match configured model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_mismatch_model",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)

    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    mfg_data = struct.pack("<HB16s", 0, 1, TEST_UUID.bytes)
    mock_adv = MagicMock()
    mock_adv.manufacturer_data = {0x055A: mfg_data}

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=mock_adv,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.asyncio
async def test_setup_entry_device_mismatch_uuid(hass: HomeAssistant) -> None:
    """Test setup raises ConfigEntryError when advertisement UUID does not match configured UUID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_mismatch_uuid",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)

    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    other_uuid = UUID("99999999-9999-9999-9999-999999999999")
    mfg_data = struct.pack("<HB16s", 5, 1, other_uuid.bytes)
    mock_adv = MagicMock()
    mock_adv.manufacturer_data = {0x055A: mfg_data}

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=mock_adv,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.asyncio
async def test_setup_entry_device_unregistered(hass: HomeAssistant) -> None:
    """Test setup raises ConfigEntryNotReady when advertisement indicates device has been reset."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_unregistered",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)

    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    mfg_data = struct.pack("<HB16s", 5, 0, TEST_UUID.bytes)
    mock_adv = MagicMock()
    mock_adv.manufacturer_data = {0x055A: mfg_data}

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=mock_adv,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.asyncio
async def test_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """Test setup raises ConfigEntryAuthFailed when authentication fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_auth_failed",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)

    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=None,
        ),
        patch.object(
            sesame_ble.SesameDeviceWrapper,
            "async_connect",
            side_effect=sesame_ble.SesameAuthenticationError("Invalid secret key"),
        ),
        patch.object(
            sesame_ble.SesameDeviceWrapper,
            "async_disconnect",
            new_callable=AsyncMock,
        ) as mock_disconnect,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    mock_disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_entry_connection_failed(hass: HomeAssistant) -> None:
    """Test setup raises ConfigEntryNotReady when connection fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_conn_failed",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)

    mock_ble_device = MagicMock()
    mock_ble_device.address = "AA:BB:CC:DD:EE:FF"

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=None,
        ),
        patch.object(
            sesame_ble.SesameDeviceWrapper,
            "async_connect",
            side_effect=TimeoutError("BLE connect timeout"),
        ),
        patch.object(
            sesame_ble.SesameDeviceWrapper,
            "async_disconnect",
            new_callable=AsyncMock,
        ) as mock_disconnect,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_disconnect.assert_awaited_once()


def _make_wrapper(hass: HomeAssistant) -> sesame_ble.SesameDeviceWrapper:
    """Helper to create a SesameDeviceWrapper with mocked device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_wrapper_entry",
        unique_id="AA:BB:CC:DD:EE:FF",
        data={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)
    ble_device = MagicMock()
    ble_device.address = "AA:BB:CC:DD:EE:FF"
    adv_data = MagicMock()
    with patch("homeassistant.components.sesame_ble.SesameLock"):
        return sesame_ble.SesameDeviceWrapper(
            hass,
            entry,
            ble_device,
            adv_data,
            secret_key="0123456789abcdef0123456789abcdef",
            model_name="SESAME5",
        )


@pytest.mark.asyncio
async def test_wrapper_fw_version(hass: HomeAssistant) -> None:
    """Test wrapper fw_version property."""
    wrapper = _make_wrapper(hass)
    wrapper.device.fw_version = "2.1.0"
    assert wrapper.fw_version == "2.1.0"


@pytest.mark.asyncio
async def test_wrapper_notify_update_listeners_exception(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that exceptions in update listeners are logged and caught."""
    wrapper = _make_wrapper(hass)

    def broken_listener() -> None:
        raise RuntimeError("boom")

    wrapper.register_update_listener(broken_listener)
    wrapper.notify_update_listeners()
    assert "Error in Sesame update listener" in caplog.text


@pytest.mark.asyncio
async def test_wrapper_handle_status_update(hass: HomeAssistant) -> None:
    """Test _handle_status_update triggers update listeners."""
    wrapper = _make_wrapper(hass)
    called = []
    wrapper.register_update_listener(lambda: called.append(True))
    wrapper._handle_status_update(wrapper.device, None)
    assert len(called) == 1


@pytest.mark.asyncio
async def test_wrapper_async_connect_success(hass: HomeAssistant) -> None:
    """Test async_connect connects, logs in, and notifies listeners."""
    wrapper = _make_wrapper(hass)
    wrapper.device.is_connected = False
    wrapper.device.is_logged_in = False
    wrapper.device.connect = AsyncMock()
    wrapper.device.login = AsyncMock()
    called = []
    wrapper.register_update_listener(lambda: called.append(True))

    await wrapper.async_connect()

    wrapper.device.connect.assert_awaited_once()
    wrapper.device.login.assert_awaited_once()
    assert len(called) == 1


@pytest.mark.asyncio
async def test_wrapper_async_connect_unloading(hass: HomeAssistant) -> None:
    """Test async_connect aborts immediately when unloading."""
    wrapper = _make_wrapper(hass)
    wrapper._is_unloading = True
    wrapper.device.connect = AsyncMock()

    await wrapper.async_connect()

    wrapper.device.connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrapper_async_connect_unloading_during_lock(
    hass: HomeAssistant,
) -> None:
    """Test async_connect aborts if unloading is set while waiting on lock."""
    wrapper = _make_wrapper(hass)
    wrapper.device.connect = AsyncMock()

    async with wrapper._connect_lock:
        task = asyncio.create_task(wrapper.async_connect())
        await asyncio.sleep(0)
        wrapper._is_unloading = True

    await task
    wrapper.device.connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrapper_async_reconnect_unloading(hass: HomeAssistant) -> None:
    """Test async_reconnect aborts immediately when unloading."""
    wrapper = _make_wrapper(hass)
    wrapper._is_unloading = True
    with patch.object(wrapper, "async_connect", new_callable=AsyncMock) as mock_connect:
        await wrapper.async_reconnect()
        mock_connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrapper_properties_and_cancel_reconnect(hass: HomeAssistant) -> None:
    """Test is_unloading, is_connecting properties and cancel_reconnect."""
    wrapper = _make_wrapper(hass)
    assert wrapper.is_unloading is False
    assert wrapper.is_connecting is False

    mock_timer = MagicMock()
    mock_task = MagicMock()
    wrapper._reconnect_timer = mock_timer
    wrapper._reconnect_task = mock_task

    wrapper.cancel_reconnect()

    mock_timer.assert_called_once()
    mock_task.cancel.assert_called_once()
    assert wrapper._reconnect_timer is None
    assert wrapper._reconnect_task is None


@pytest.mark.asyncio
async def test_wrapper_async_connect_clears_pending_reconnect_timer(
    hass: HomeAssistant,
) -> None:
    """Test that a successful async_connect clears any pending reconnect timer."""
    wrapper = _make_wrapper(hass)
    wrapper.device.is_connected = False
    wrapper.device.is_logged_in = False
    wrapper.device.connect = AsyncMock()
    wrapper.device.login = AsyncMock()
    mock_timer = MagicMock()
    wrapper._reconnect_timer = mock_timer

    await wrapper.async_connect()

    mock_timer.assert_called_once()
    assert wrapper._reconnect_timer is None


@pytest.mark.asyncio
async def test_wrapper_reconnect_backoff_and_timer_firing(
    hass: HomeAssistant,
) -> None:
    """Test retry backoff scheduling and timer firing on reconnection failure."""
    wrapper = _make_wrapper(hass)
    wrapper.device.is_connected = False

    with patch.object(
        wrapper, "async_connect", side_effect=RuntimeError("BLE connection failed")
    ) as mock_connect:
        wrapper.schedule_reconnect()
        await hass.async_block_till_done()

        mock_connect.assert_awaited_once()
        assert wrapper._reconnect_timer is not None
        assert wrapper._reconnect_backoff == 4.0

        # While timer is pending, subsequent schedule_reconnect calls are ignored
        wrapper.schedule_reconnect()
        assert mock_connect.await_count == 1

        # Fire timer and verify next reconnect attempt is triggered and reschedules
        with patch.object(
            wrapper, "schedule_reconnect", wraps=wrapper.schedule_reconnect
        ) as mock_schedule:
            wrapper._handle_reconnect_timer()
            mock_schedule.assert_called_once()
            await hass.async_block_till_done()
            assert wrapper._reconnect_backoff == 8.0
            assert wrapper._reconnect_timer is not None
            wrapper.cancel_reconnect()


@pytest.mark.asyncio
async def test_wrapper_schedule_retry_timer_guards(hass: HomeAssistant) -> None:
    """Test _schedule_retry_timer aborts when unloading, connected, or replaces existing timer."""
    wrapper = _make_wrapper(hass)
    wrapper._is_unloading = True
    wrapper._schedule_retry_timer(5.0)
    assert wrapper._reconnect_timer is None

    wrapper._is_unloading = False
    wrapper.device.is_connected = True
    wrapper._schedule_retry_timer(5.0)
    assert wrapper._reconnect_timer is None

    wrapper.device.is_connected = False
    old_timer = MagicMock()
    wrapper._reconnect_timer = old_timer
    wrapper._schedule_retry_timer(5.0)
    old_timer.assert_called_once()
    assert wrapper._reconnect_timer is not None
    wrapper.cancel_reconnect()


@pytest.mark.asyncio
async def test_wrapper_schedule_reconnect_guards(hass: HomeAssistant) -> None:
    """Test schedule_reconnect guards when connected, reconnecting, or unloading."""
    wrapper = _make_wrapper(hass)
    wrapper.device.is_connected = True
    wrapper.schedule_reconnect()
    assert wrapper._reconnect_task is None

    wrapper.device.is_connected = False
    wrapper._is_unloading = True
    wrapper.schedule_reconnect()
    assert wrapper._reconnect_task is None

    wrapper._is_unloading = False
    mock_running_task = MagicMock()
    mock_running_task.done.return_value = False
    wrapper._reconnect_task = mock_running_task
    wrapper.schedule_reconnect()
    assert wrapper._reconnect_task is mock_running_task


@pytest.mark.asyncio
async def test_wrapper_unexpected_disconnect_callback(hass: HomeAssistant) -> None:
    """Test _handle_unexpected_disconnect notifies listeners and schedules reconnect."""
    wrapper = _make_wrapper(hass)
    wrapper.device.is_connected = False
    called: list[bool] = []
    wrapper.register_update_listener(lambda: called.append(True))

    with patch.object(wrapper, "schedule_reconnect") as mock_sched:
        wrapper._handle_unexpected_disconnect()
        assert len(called) == 1
        mock_sched.assert_called_once()


@pytest.mark.asyncio
async def test_wrapper_reconnect_finally_does_not_clear_newer_task(
    hass: HomeAssistant,
) -> None:
    """Test that reconnect finally block does not clear a newer reconnect task."""
    wrapper = _make_wrapper(hass)
    wrapper.device.is_connected = False
    newer_task = MagicMock()

    async def fake_connect() -> None:
        wrapper._reconnect_task = newer_task

    with patch.object(wrapper, "async_connect", side_effect=fake_connect):
        await wrapper._async_reconnect_with_backoff()

    assert wrapper._reconnect_task is newer_task
