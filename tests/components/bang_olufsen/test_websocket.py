"""Test the Bang & Olufsen WebSocket listener."""

import logging
from unittest.mock import AsyncMock, Mock

from mozart_api.models import SoftwareUpdateState
import pytest

from homeassistant.components.bang_olufsen.const import (
    BANG_OLUFSEN_WEBSOCKET_EVENT,
    CONNECTION_STATUS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import TEST_NAME

from tests.common import MockConfigEntry


async def test_connection(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test on_connection and on_connection_lost logs and calls correctly."""

    mock_mozart_client.websocket_connected = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    connection_callback = mock_mozart_client.get_on_connection.call_args[0][0]

    caplog.set_level(logging.DEBUG)

    mock_connection_callback = Mock()

    async_dispatcher_connect(
        hass,
        f"{mock_config_entry.unique_id}_{CONNECTION_STATUS}",
        mock_connection_callback,
    )

    # Call the WebSocket connection status method
    connection_callback()
    await hass.async_block_till_done()

    mock_connection_callback.assert_called_once_with(True)
    assert f"Connected to the {TEST_NAME} notification channel" in caplog.text


async def test_connection_lost(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test on_connection_lost logs and calls correctly."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    connection_lost_callback = mock_mozart_client.get_on_connection_lost.call_args[0][0]

    mock_connection_lost_callback = Mock()

    async_dispatcher_connect(
        hass,
        f"{mock_config_entry.unique_id}_{CONNECTION_STATUS}",
        mock_connection_lost_callback,
    )

    connection_lost_callback()
    await hass.async_block_till_done()

    mock_connection_lost_callback.assert_called_once_with(False)
    assert f"Lost connection to the {TEST_NAME}" in caplog.text


async def test_on_software_update_state(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test software version is updated through on_software_update_state."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    software_update_state_callback = (
        mock_mozart_client.get_software_update_state_notifications.call_args[0][0]
    )

    # Trigger the notification
    await software_update_state_callback(SoftwareUpdateState())

    await hass.async_block_till_done()

    assert mock_config_entry.unique_id
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.unique_id)}
        )
    )
    assert device.sw_version == "1.0.0"


async def test_on_all_notifications_raw(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test on_all_notifications_raw logs and fires as expected."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    all_notifications_raw_callback = (
        mock_mozart_client.get_all_notifications_raw.call_args[0][0]
    )

    raw_notification = {
        "eventData": {
            "default": {"level": 40},
            "level": {"level": 40},
            "maximum": {"level": 100},
            "muted": {"muted": False},
        },
        "eventType": "WebSocketEventVolume",
    }

    # Get device ID for the modified notification that is sent as an event and in the log
    assert mock_config_entry.unique_id
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.unique_id)}
        )
    )
    raw_notification_full = {
        "device_id": device.id,
        "serial_number": int(mock_config_entry.unique_id),
        **raw_notification,
    }

    caplog.set_level(logging.DEBUG)

    mock_event_callback = Mock()

    # Listen to BANG_OLUFSEN_WEBSOCKET_EVENT events
    hass.bus.async_listen(BANG_OLUFSEN_WEBSOCKET_EVENT, mock_event_callback)

    # Trigger the notification
    all_notifications_raw_callback(raw_notification)
    await hass.async_block_till_done()

    assert str(raw_notification_full) in caplog.text

    mocked_call = mock_event_callback.call_args[0][0].as_dict()
    assert mocked_call["event_type"] == BANG_OLUFSEN_WEBSOCKET_EVENT
    assert mocked_call["data"] == raw_notification_full
