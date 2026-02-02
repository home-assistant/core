"""Test the Bang & Olufsen WebSocket listener."""

import logging
from unittest.mock import AsyncMock, Mock

from mozart_api.models import (
    PairedRemote,
    PairedRemoteResponse,
    SoftwareUpdateState,
    WebsocketNotificationTag,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bang_olufsen.const import (
    BANG_OLUFSEN_WEBSOCKET_EVENT,
    CONNECTION_STATUS,
    DOMAIN,
    WebsocketNotification,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import (
    TEST_NAME,
    TEST_REMOTE_SERIAL,
    TEST_REMOTE_SERIAL_PAIRED,
    TEST_SERIAL_NUMBER,
)
from .util import get_button_entity_ids, get_remote_entity_ids

from tests.common import MockConfigEntry


async def test_connection(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    integration: None,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on_connection and on_connection_lost logs and calls correctly."""
    mock_mozart_client.websocket_connected = True

    connection_callback = mock_mozart_client.get_on_connection.call_args[0][0]

    caplog.set_level(logging.DEBUG)

    mock_connection_callback = Mock()

    async_dispatcher_connect(
        hass,
        f"{DOMAIN}_{mock_config_entry.unique_id}_{CONNECTION_STATUS}",
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
    integration: None,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on_connection_lost logs and calls correctly."""
    connection_lost_callback = mock_mozart_client.get_on_connection_lost.call_args[0][0]

    mock_connection_lost_callback = Mock()

    async_dispatcher_connect(
        hass,
        f"{DOMAIN}_{mock_config_entry.unique_id}_{CONNECTION_STATUS}",
        mock_connection_lost_callback,
    )

    connection_lost_callback()
    await hass.async_block_till_done()

    mock_connection_lost_callback.assert_called_once_with(False)
    assert f"Lost connection to the {TEST_NAME}" in caplog.text


async def test_on_software_update_state(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    integration: None,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test software version is updated through on_software_update_state."""
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


async def test_on_remote_control_already_added(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the integration does nothing when a remote that already has a device triggers a check."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check device and API call count
    assert mock_mozart_client.get_bluetooth_remotes.call_count == 1
    assert device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)})

    # Check number of entities (remote and button events and media_player)
    assert (
        len(list(entity_registry.entities.keys()))
        == len(get_remote_entity_ids()) + len(get_button_entity_ids()) + 1
    )
    remote_callback = mock_mozart_client.get_notification_notifications.call_args[0][0]

    # Trigger the notification
    await remote_callback(
        WebsocketNotificationTag(
            value=WebsocketNotification.REMOTE_CONTROL_DEVICES.value
        )
    )

    await hass.async_block_till_done()

    # Check device and API call count (triggered once by the WebSocket notification)
    assert mock_mozart_client.get_bluetooth_remotes.call_count == 2
    assert device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)})

    # Check number of entities
    entity_ids_available = list(entity_registry.entities.keys())

    assert (
        len(entity_ids_available)
        == len(get_remote_entity_ids()) + len(get_button_entity_ids()) + 1
    )
    assert entity_ids_available == snapshot


async def test_on_remote_control_paired(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the integration reloads when a new remote has been paired."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check device and API call count
    assert mock_mozart_client.get_bluetooth_remotes.call_count == 1
    assert device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)})

    # Check number of entities (button events and media_player)
    assert (
        len(list(entity_registry.entities.keys()))
        == len(get_remote_entity_ids()) + len(get_button_entity_ids()) + 1
    )
    # "Pair" a new remote
    mock_mozart_client.get_bluetooth_remotes.return_value = PairedRemoteResponse(
        items=[
            # Already paired
            PairedRemote(
                address="",
                app_version="1.0.0",
                battery_level=50,
                connected=True,
                serial_number=TEST_REMOTE_SERIAL,
                name="BEORC",
            ),
            # Not paired yet
            PairedRemote(
                address="",
                app_version="1.0.0",
                battery_level=50,
                connected=True,
                serial_number="66666666",
                name="BEORC",
            ),
        ]
    )
    remote_callback = mock_mozart_client.get_notification_notifications.call_args[0][0]

    # Trigger the notification
    await remote_callback(
        WebsocketNotificationTag(
            value=WebsocketNotification.REMOTE_CONTROL_DEVICES.value
        )
    )
    await hass.async_block_till_done()

    # Check device and API call count
    assert mock_mozart_client.get_bluetooth_remotes.call_count == 3
    assert device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)})
    assert device_registry.async_get_device(
        {(DOMAIN, f"66666666_{TEST_SERIAL_NUMBER}")}
    )

    # Check logger
    assert (
        f"A Beoremote One has been paired or unpaired to {mock_config_entry.title}. Reloading config entry to add device and entities"
        in caplog.text
    )

    # Check number of entities (remote and button events and media_player)
    entity_ids_available = list(entity_registry.entities.keys())

    assert (
        len(entity_ids_available)
        == len(get_remote_entity_ids())
        + len(get_remote_entity_ids())
        + len(get_button_entity_ids())
        + 1
    )
    assert entity_ids_available == snapshot


async def test_on_remote_control_unpaired(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the integration reloads when a remote has been unpaired."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check device and API call count
    assert mock_mozart_client.get_bluetooth_remotes.call_count == 1
    assert device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)})

    # Check number of entities (button events and media_player)
    assert (
        len(list(entity_registry.entities.keys()))
        == len(get_remote_entity_ids()) + len(get_button_entity_ids()) + 1
    )
    # "Unpair" the remote
    mock_mozart_client.get_bluetooth_remotes.return_value = PairedRemoteResponse(
        items=[]
    )
    remote_callback = mock_mozart_client.get_notification_notifications.call_args[0][0]

    # Trigger the notification
    await remote_callback(
        WebsocketNotificationTag(
            value=WebsocketNotification.REMOTE_CONTROL_DEVICES.value
        )
    )
    await hass.async_block_till_done()

    # Check device and API call count
    assert mock_mozart_client.get_bluetooth_remotes.call_count == 3
    assert (
        device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)}) is None
    )

    # Check logger
    assert (
        f"A Beoremote One has been paired or unpaired to {mock_config_entry.title}. Reloading config entry to add device and entities"
        in caplog.text
    )

    # Check number of entities (button events and media_player)
    entity_ids_available = list(entity_registry.entities.keys())

    assert len(entity_ids_available) == +len(get_button_entity_ids()) + 1
    assert entity_ids_available == snapshot


# async def test_setup_entry_remote_unpaired(
#     hass: HomeAssistant,
#     device_registry: DeviceRegistry,
#     entity_registry: EntityRegistry,
#     mock_config_entry: MockConfigEntry,
#     mock_mozart_client: AsyncMock,
# ) -> None:
#     """Test async_setup_entry where a remote has been unpaired and should be removed."""

#     # Load entry
#     mock_config_entry.add_to_hass(hass)
#     await hass.config_entries.async_setup(mock_config_entry.entry_id)

#     # Check device and API call count (called once during init and once in async_setup_entry in event.py)
#     assert mock_mozart_client.get_bluetooth_remotes.call_count == 2
#     assert device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)})

#     # Check entities
#     for entity_id in get_remote_entity_ids():
#         assert entity_registry.async_get(entity_id)

#     # "Unpair" the remote and reload config_entry
#     mock_mozart_client.get_bluetooth_remotes.return_value = PairedRemoteResponse(
#         items=[]
#     )
#     hass.config_entries.async_schedule_reload(mock_config_entry.entry_id)

#     # Check device and API call count
#     assert mock_mozart_client.get_bluetooth_remotes.call_count == 4
#     assert not device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)})

#     # Check entities
#     for entity_id in get_remote_entity_ids():
#         assert not entity_registry.async_get(entity_id)


async def test_on_all_notifications_raw(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: DeviceRegistry,
    integration: None,
    mock_mozart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on_all_notifications_raw logs and fires as expected."""
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
