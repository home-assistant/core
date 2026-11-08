"""Tests for the System Bridge notify platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.notification import Notification
from systembridgeconnector.models.response import Response

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.discovery import async_load_platform

from . import FIXTURE_REQUEST_ID

ERROR_RESPONSE = Response(
    id=FIXTURE_REQUEST_ID,
    type=EventType.ERROR,
    subtype="BAD_REQUEST",
    message="Title is required",
    data={},
)


@pytest.fixture(autouse=True)
def notify_only() -> Generator[None]:
    """Enable only the notify platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.NOTIFY],
    ):
        yield


@pytest.fixture
def legacy_notify() -> Generator[None]:
    """Load the legacy notify platform."""
    with patch(
        "homeassistant.helpers.discovery.async_load_platform",
        wraps=async_load_platform,
    ):
        yield


@pytest.mark.usefixtures("mock_version", "mock_websocket_client")
async def test_notify_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the notify platform."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_version")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_send_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
) -> None:
    """Test sending a message."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("notify.hostname")
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: "notify.hostname",
            ATTR_MESSAGE: "World",
            ATTR_TITLE: "Hello",
        },
        blocking=True,
    )

    state = hass.states.get("notify.hostname")
    assert state
    assert state.state == "2009-02-13T23:31:30+00:00"

    mock_websocket_client.send_notification.assert_awaited_once_with(
        Notification(title="Hello", message="World")
    )


@pytest.mark.usefixtures("mock_version", "legacy_notify")
async def test_legacy_notify_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
) -> None:
    """Test sending a message with the legacy notify service."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "system_bridge_hostname",
        {
            ATTR_MESSAGE: "World",
            ATTR_DATA: {
                "actions": [{"command": "test", "label": "Test"}],
                "icon": "mdi:test",
                "image": "https://example.com/image.png",
                "timeout": 10,
                ATTR_TITLE: "Hello",
            },
        },
        blocking=True,
    )

    mock_websocket_client.send_notification.assert_awaited_once_with(
        Notification(
            actions=[{"command": "test", "label": "Test"}],
            icon="mdi:test",
            image="https://example.com/image.png",
            message="World",
            timeout=10,
            title="Hello",
        )
    )


@pytest.mark.usefixtures("mock_version")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
@pytest.mark.parametrize(
    ("side_effect", "translation_key", "placeholders"),
    [
        pytest.param(
            ConnectionClosedException,
            "send_message_failed",
            {"title": "TestSystem", "host": "127.0.0.1"},
            id="connection_closed",
        ),
        pytest.param(
            [ERROR_RESPONSE],
            "notification_failed",
            {"error": "Title is required"},
            id="error_response",
        ),
    ],
)
async def test_send_message_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    side_effect: type[Exception] | list[Response],
    translation_key: str,
    placeholders: dict[str, str],
) -> None:
    """Test sending a message that fails raises and isn't recorded."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_websocket_client.send_notification.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as e:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.hostname",
                ATTR_MESSAGE: "World",
                ATTR_TITLE: "Hello",
            },
            blocking=True,
        )

    mock_websocket_client.send_notification.assert_awaited_once_with(
        Notification(title="Hello", message="World")
    )
    assert e.value.translation_key == translation_key
    assert e.value.translation_placeholders == placeholders
    state = hass.states.get("notify.hostname")
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_version", "legacy_notify")
async def test_legacy_notify_service_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
) -> None:
    """Test the legacy notify service raises when the notification fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_websocket_client.send_notification.return_value = ERROR_RESPONSE

    with pytest.raises(HomeAssistantError) as e:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "system_bridge_hostname",
            {ATTR_MESSAGE: "World"},
            blocking=True,
        )

    assert e.value.translation_key == "notification_failed"
    assert e.value.translation_placeholders == {"error": "Title is required"}


@pytest.mark.usefixtures("mock_version", "legacy_notify")
async def test_legacy_notify_service_unloaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
) -> None:
    """Test the legacy notify service doesn't use the connection after unload."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    with pytest.raises(HomeAssistantError) as e:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "system_bridge_hostname",
            {ATTR_MESSAGE: "World"},
            blocking=True,
        )

    assert e.value.translation_key == "entry_not_loaded"
    assert e.value.translation_placeholders == {"entry_id": mock_config_entry.entry_id}
    mock_websocket_client.send_notification.assert_not_awaited()
