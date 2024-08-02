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


@pytest.mark.parametrize(
    ("websocket_connected", "method", "logger_level", "message"),
    [
        (
            True,
            "on_connection",
            "debug",
            ("Connected to the %s notification channel", TEST_NAME),
        ),
        (
            False,
            "on_connection_lost",
            "error",
            ("Lost connection to the %s", TEST_NAME),
        ),
    ],
)
async def test_connection(
    websocket_connected,
    method,
    logger_level,
    message,
    hass: HomeAssistant,
    mock_config_entry,
    mock_mozart_client,
) -> None:
    """Test on_connection and on_connection_lost logs and calls correctly."""
    mock_mozart_client.websocket_connected = websocket_connected

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    websocket = hass.data[DOMAIN][mock_config_entry.entry_id].websocket

    with (
        patch(
            f"homeassistant.components.bang_olufsen.websocket._LOGGER.{logger_level}"
        ) as mock_logger,
        patch(
            "homeassistant.components.bang_olufsen.websocket.async_dispatcher_send"
        ) as mock_dispatch,
    ):
        # Call the WebSocket connection status method
        getattr(websocket, method)()

        mock_logger.assert_called_once_with(*message)
        mock_dispatch.assert_called_once_with(
            hass,
            f"{mock_config_entry.unique_id}_{CONNECTION_STATUS}",
            websocket_connected,
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
    websocket = hass.data[DOMAIN][mock_config_entry.entry_id].websocket

    # Check if the device can be retrieved
    if not initial_device:
        websocket._device = None
    else:
        # The sw version gets set exclusively by this notification, so will initially be None
        assert websocket._device.sw_version is None

    # Trigger the notification
    await websocket.on_software_update_state(SoftwareUpdateState())

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
        websocket.on_all_notifications_raw(raw_notification)

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
