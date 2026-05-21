"""Tests for the coordinator of the WLED integration."""

import asyncio
from collections.abc import Callable
from copy import deepcopy
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from wled import (
    Device as WLEDDevice,
    WLEDConnectionClosedError,
    WLEDConnectionError,
    WLEDEmptyResponseError,
    WLEDError,
    WLEDInvalidResponseError,
    WLEDUnsupportedVersionError,
)

from homeassistant.components.wled.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_not_supporting_websocket(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Ensure no WebSocket attempt is made if non-WebSocket device."""
    assert mock_wled.connect.call_count == 0


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_websocket_already_connected(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure no a second WebSocket connection is made, if already connected."""
    assert mock_wled.connect.call_count == 1

    mock_wled.connected = True

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_wled.connect.call_count == 1


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_websocket_connect_error_no_listen(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure we don't start listening if WebSocket connection failed."""
    assert mock_wled.connect.call_count == 1
    assert mock_wled.listen.call_count == 1

    mock_wled.connect.side_effect = WLEDConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_wled.connect.call_count == 2
    assert mock_wled.listen.call_count == 1


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_websocket(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test WebSocket connection."""
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_ON

    # There is no Future in place yet...
    assert mock_wled.connect.call_count == 1
    assert mock_wled.listen.call_count == 1
    assert mock_wled.disconnect.call_count == 1

    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback: Callable[[WLEDDevice], None]):
        connection_connected.set_result(callback)
        await connection_finished

    # Mock out wled.listen with a Future
    mock_wled.listen.side_effect = connect

    # Mock out the event bus
    mock_bus = MagicMock()
    hass.bus = mock_bus

    # Next refresh it should connect
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    callback = await connection_connected

    # Connected to WebSocket, disconnect not called
    # listening for Home Assistant to stop
    assert mock_wled.connect.call_count == 2
    assert mock_wled.listen.call_count == 2
    assert mock_wled.disconnect.call_count == 1
    assert mock_bus.async_listen_once.call_count == 1
    assert (
        mock_bus.async_listen_once.call_args_list[0][0][0] == EVENT_HOMEASSISTANT_STOP
    )
    assert (
        mock_bus.async_listen_once.call_args_list[0][0][1].__name__ == "close_websocket"
    )
    assert mock_bus.async_listen_once.return_value.call_count == 0

    # Send update from WebSocket
    # Note we may still update() during websocket setup
    # so update it too.
    mock_wled.update.return_value.state.on = False
    updated_device = deepcopy(mock_wled.update.return_value)
    callback(updated_device)
    await hass.async_block_till_done()

    # Check if entity updated
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_OFF

    # Listening for changes on websocket, polling is suspended
    num_updates_before_websocket = mock_wled.update.call_count
    for _scans in range(4):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert mock_wled.update.call_count == num_updates_before_websocket

    # Resolve Future with a closed connection.
    connection_finished.set_exception(WLEDConnectionClosedError)
    await hass.async_block_till_done()

    # Disconnect called, unsubbed Home Assistant stop listener
    assert mock_wled.disconnect.call_count == 2
    assert mock_bus.async_listen_once.return_value.call_count == 1

    # Light still available, as polling takes over
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_websocket_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test WebSocket connection erroring out, marking lights unavailable."""
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_ON

    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback: Callable[[WLEDDevice], None]):
        connection_connected.set_result(None)
        await connection_finished

    mock_wled.listen.side_effect = connect
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await connection_connected

    # Resolve listen() with an error. This causes polling
    # to take over so fail polling update() too
    mock_wled.update.side_effect = WLEDError
    mock_wled.listen.side_effect = WLEDError
    connection_finished.set_exception(WLEDError)
    await hass.async_block_till_done()

    # Light no longer available as an error occurred
    # and polling couldn't take over.
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Light becomes available after polling takes over
    mock_wled.update.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_ON


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_websocket_disconnect_on_home_assistant_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure WebSocket is disconnected when Home Assistant stops."""
    assert mock_wled.disconnect.call_count == 1
    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback: Callable[[WLEDDevice], None]):
        connection_connected.set_result(None)
        await connection_finished

    mock_wled.listen.side_effect = connect
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await connection_connected

    assert mock_wled.disconnect.call_count == 1

    hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert mock_wled.disconnect.call_count == 2


async def test_fail_when_other_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Ensure entry fails to setup when mac mismatch."""
    device = mock_wled.update.return_value
    device.info.mac_address = "invalid"

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason
    assert (
        "MAC address does not match the configured device." in mock_config_entry.reason
    )


@pytest.mark.parametrize(
    (
        "exception",
        "expected_state",
        "expected_error_reason_translation_key",
        "expected_log_message",
    ),
    [
        pytest.param(
            WLEDUnsupportedVersionError(
                "Unsupported firmware version 0.14.0-b1. Minimum required version is 0.14.0. "
                "Please update your WLED device."
            ),
            ConfigEntryState.SETUP_ERROR,
            "unsupported_version",
            "Unsupported firmware version 0.14.0-b1. Minimum required version is 0.14.0. Please update your WLED device.",
            id="unsupported_version",
        ),
        pytest.param(
            WLEDConnectionError,
            ConfigEntryState.SETUP_RETRY,
            None,
            "Error communicating with WLED API:",
            id="connection_error",
        ),
        pytest.param(
            WLEDInvalidResponseError(
                "Received a non-UTF-8 response from request: GET /json"
            ),
            ConfigEntryState.SETUP_RETRY,
            None,
            "Invalid response from WLED API: ",
            id="invalid_response",
        ),
        pytest.param(
            WLEDInvalidResponseError(
                "Received a non-UTF-8 response from request: GET /presets.json"
            ),
            ConfigEntryState.SETUP_RETRY,
            None,
            "Failed to download presets from device. Check preset configurations in WLED UI.",
            id="invalid_response_presets",
        ),
        pytest.param(
            WLEDEmptyResponseError(
                "WLED device at X returned an empty API response on full update"
            ),
            ConfigEntryState.SETUP_RETRY,
            None,
            "Invalid response from WLED API: ",
            id="empty_response_full_update",
        ),
        pytest.param(
            WLEDEmptyResponseError(
                "WLED device at X returned an empty API response on presets update"
            ),
            ConfigEntryState.SETUP_RETRY,
            None,
            "Failed to download presets from device. Check preset configurations in WLED UI.",
            id="empty_response_presets_update",
        ),
    ],
)
async def test_errors_on_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    exception: Exception,
    expected_state: ConfigEntryState,
    expected_error_reason_translation_key: str,
    expected_log_message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure entry fails to setup when unsupported version."""
    mock_wled.update.side_effect = exception

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state

    assert (
        mock_config_entry.error_reason_translation_key
        == expected_error_reason_translation_key
    )
    assert expected_log_message in caplog.text
