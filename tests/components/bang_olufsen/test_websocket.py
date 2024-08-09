"""Test the Bang & Olufsen WebSocket listener."""

from unittest.mock import patch

from mozart_api.models import SoftwareUpdateState
import pytest

from homeassistant.components.bang_olufsen.const import (
    BANG_OLUFSEN_WEBSOCKET_EVENT,
    CONNECTION_STATUS,
    DOMAIN,
)
from homeassistant.components.bang_olufsen.util import get_device
from homeassistant.core import HomeAssistant

from .const import TEST_NAME


async def test_connection(
    hass: HomeAssistant, mock_config_entry, mock_mozart_client
) -> None:
    """Test on_connection and on_connection_lost logs and calls correctly."""
    mock_mozart_client.websocket_connected = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    connection_callback = mock_mozart_client.get_on_connection.call_args[0][0]

    with (
        patch(
            "homeassistant.components.bang_olufsen.websocket._LOGGER.debug"
        ) as mock_logger,
        patch(
            "homeassistant.components.bang_olufsen.websocket.async_dispatcher_send"
        ) as mock_dispatch,
    ):
        # Call the WebSocket connection status method
        connection_callback()

        mock_logger.assert_called_once_with(
            "Connected to the %s notification channel", TEST_NAME
        )
        mock_dispatch.assert_called_once_with(
            hass,
            f"{mock_config_entry.unique_id}_{CONNECTION_STATUS}",
            True,
        )


async def test_connection_lost(
    hass: HomeAssistant, mock_config_entry, mock_mozart_client
) -> None:
    """Test on_connection_lost logs and calls correctly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    connection_lost_callback = mock_mozart_client.get_on_connection_lost.call_args[0][0]

    with (
        patch(
            "homeassistant.components.bang_olufsen.websocket._LOGGER.error"
        ) as mock_logger,
        patch(
            "homeassistant.components.bang_olufsen.websocket.async_dispatcher_send"
        ) as mock_dispatch,
    ):
        # Call the WebSocket connection status method
        connection_lost_callback()

        mock_logger.assert_called_once_with("Lost connection to the %s", TEST_NAME)
        mock_dispatch.assert_called_once_with(
            hass,
            f"{mock_config_entry.unique_id}_{CONNECTION_STATUS}",
            False,
        )


@pytest.mark.parametrize(
    ("initial_device"),
    [
        (True),
        (False),
    ],
)
async def test_on_software_update_state(
    initial_device, hass: HomeAssistant, mock_config_entry, mock_mozart_client
) -> None:
    """Test software version is updated through on_software_update_state."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    software_update_state_callback = (
        mock_mozart_client.get_software_update_state_notifications.call_args[0][0]
    )

    websocket = hass.data[DOMAIN][mock_config_entry.entry_id].websocket

    # Check if the device can be retrieved
    if not initial_device:
        websocket._device = None
    else:
        # The sw version gets set exclusively by this notification, so will initially be None
        assert websocket._device.sw_version is None

    # Trigger the notification
    await software_update_state_callback(SoftwareUpdateState())

    device = get_device(hass, mock_config_entry.unique_id)
    assert device.sw_version == "1.0.0"


@pytest.mark.parametrize(
    ("initial_device"),
    [
        (True),
        (False),
    ],
)
async def test_on_all_notifications_raw(
    initial_device, hass: HomeAssistant, mock_config_entry, mock_mozart_client
) -> None:
    """Test on_all_notifications_raw logs and fires as expected."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    all_notifications_raw_callback = (
        mock_mozart_client.get_all_notifications_raw.call_args[0][0]
    )

    websocket = hass.data[DOMAIN][mock_config_entry.entry_id].websocket

    # Check if the device can be retrieved
    if not initial_device:
        websocket._device = None

    raw_notification = {
        "eventData": {
            "default": {"level": 40},
            "level": {"level": 40},
            "maximum": {"level": 100},
            "muted": {"muted": False},
        },
        "eventType": "WebSocketEventVolume",
    }

    # Trigger the notification
    with (
        patch(
            "homeassistant.components.bang_olufsen.websocket._LOGGER.debug"
        ) as mock_logger,
        patch("homeassistant.core.EventBus.async_fire") as mock_fire,
    ):
        all_notifications_raw_callback(raw_notification)

        # Add device_id and serial_number to notification
        raw_notification.update(
            {
                "device_id": websocket._device.id,
                "serial_number": mock_config_entry.unique_id,
            }
        )

        mock_logger.assert_called_once_with("%s", raw_notification)
        mock_fire.assert_called_once_with(
            BANG_OLUFSEN_WEBSOCKET_EVENT, raw_notification
        )
