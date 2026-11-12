"""Tests for the System Bridge notify platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.notification import Notification, NotificationButton
from systembridgeconnector.models.response import Response

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.components.system_bridge.notify import async_get_service
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_NAME,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import entity_registry as er, issue_registry as ir
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
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test sending a message with the deprecated legacy notify service."""
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
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_notify_action_system_bridge_hostname"
    )
    assert issue
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.translation_placeholders
    assert issue.translation_placeholders["action"] == "notify.system_bridge_hostname"


@pytest.mark.usefixtures("mock_version")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
@pytest.mark.parametrize(
    ("data", "notification", "response_data", "response"),
    [
        pytest.param(
            {ATTR_MESSAGE: "World"},
            Notification(title=ATTR_TITLE_DEFAULT, message="World"),
            {"id": 1},
            {"id": 1},
            id="message_only",
        ),
        pytest.param(
            {
                ATTR_MESSAGE: "World",
                ATTR_TITLE: "Hello",
                "icon": "dialog-information",
                "urgency": "critical",
                "duration": {"seconds": 10},
                "buttons": [
                    {"id": "yes", "label": "Yes"},
                    {"id": "no", "label": "No"},
                ],
                "sound": "/usr/share/sounds/message.oga",
                "url": "https://www.home-assistant.io",
            },
            Notification(
                title="Hello",
                message="World",
                icon="dialog-information",
                urgency="critical",
                duration=10000,
                buttons=[
                    NotificationButton(id="yes", label="Yes"),
                    NotificationButton(id="no", label="No"),
                ],
                sound="/usr/share/sounds/message.oga",
                action_url="https://www.home-assistant.io",
            ),
            {"id": 1},
            {"id": 1},
            id="all_fields",
        ),
        pytest.param(
            {ATTR_MESSAGE: "World", "path": "/home/user/Documents"},
            Notification(
                title=ATTR_TITLE_DEFAULT,
                message="World",
                action_path="/home/user/Documents",
            ),
            {"id": 1},
            {"id": 1},
            id="path",
        ),
        pytest.param(
            {ATTR_MESSAGE: "World"},
            Notification(title=ATTR_TITLE_DEFAULT, message="World"),
            {"title": ATTR_TITLE_DEFAULT, "message": "World"},
            {"id": None},
            id="no_id_before_5_20",
        ),
    ],
)
async def test_system_bridge_send_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    data: dict[str, Any],
    notification: Notification,
    response_data: dict[str, Any],
    response: dict[str, Any],
) -> None:
    """Test sending a message with the system_bridge.send_message action."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_websocket_client.send_notification.return_value = Response(
        id=FIXTURE_REQUEST_ID,
        type=EventType.NOTIFICATION_SENT,
        message="Notification sent",
        data=response_data,
    )

    result = await hass.services.async_call(
        DOMAIN,
        "send_message",
        {ATTR_ENTITY_ID: "notify.hostname", **data},
        blocking=True,
        return_response=True,
    )

    assert result == {"notify.hostname": response}
    mock_websocket_client.send_notification.assert_awaited_once_with(notification)
    state = hass.states.get("notify.hostname")
    assert state
    assert state.state == "2009-02-13T23:31:30+00:00"


@pytest.mark.usefixtures("mock_version")
@pytest.mark.parametrize(
    "data",
    [
        pytest.param({}, id="no_message"),
        pytest.param({ATTR_MESSAGE: "World", "urgency": "urgent"}, id="urgency"),
        pytest.param(
            {
                ATTR_MESSAGE: "World",
                "buttons": [{"id": str(i), "label": str(i)} for i in range(4)],
            },
            id="too_many_buttons",
        ),
        pytest.param(
            {
                ATTR_MESSAGE: "World",
                "buttons": [{"id": "default", "label": "Default"}],
            },
            id="default_button_id",
        ),
        pytest.param(
            {ATTR_MESSAGE: "World", "buttons": [{"id": "yes"}]},
            id="button_without_label",
        ),
        pytest.param(
            {
                ATTR_MESSAGE: "World",
                "url": "https://www.home-assistant.io",
                "path": "/home/user/Documents",
            },
            id="url_and_path",
        ),
    ],
)
async def test_system_bridge_send_message_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    data: dict[str, Any],
) -> None:
    """Test the system_bridge.send_message action rejects invalid data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {ATTR_ENTITY_ID: "notify.hostname", **data},
            blocking=True,
            return_response=True,
        )

    mock_websocket_client.send_notification.assert_not_awaited()


@pytest.mark.usefixtures("mock_version")
async def test_system_bridge_send_message_requires_admin(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
) -> None:
    """Test the system_bridge.send_message action needs an admin user."""
    # Control of every entity, so only the admin check can refuse the call
    hass_read_only_user.mock_policy({"entities": {"all": {"control": True}}})
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "send_message",
            {ATTR_ENTITY_ID: "notify.hostname", ATTR_MESSAGE: "World"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    mock_websocket_client.send_notification.assert_not_awaited()


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


@pytest.mark.usefixtures("mock_version", "mock_websocket_client", "legacy_notify")
async def test_legacy_notify_service_removed_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the legacy notify service is removed when the entry unloads."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, "system_bridge_hostname")

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(NOTIFY_DOMAIN, "system_bridge_hostname")


@pytest.mark.usefixtures("mock_version", "legacy_notify")
async def test_legacy_notify_service_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
) -> None:
    """Test the legacy notify service uses the new connection after a reload."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    old_coordinator = mock_config_entry.runtime_data
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data is not old_coordinator
    old_websocket_client = AsyncMock()
    old_coordinator.websocket_client = old_websocket_client

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "system_bridge_hostname",
        {ATTR_MESSAGE: "World"},
        blocking=True,
    )

    old_websocket_client.send_notification.assert_not_awaited()
    mock_websocket_client.send_notification.assert_awaited_once()


@pytest.mark.usefixtures("mock_version", "mock_websocket_client", "legacy_notify")
@pytest.mark.parametrize("owner_first", [True, False], ids=["owner", "other"])
async def test_legacy_notify_service_shared_hostname(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    owner_first: bool,
) -> None:
    """Test unloading an entry keeps the action for another with the same name."""
    other_entry = MockConfigEntry(
        title="Other",
        domain=DOMAIN,
        unique_id="other-uuid",
        version=mock_config_entry.version,
        minor_version=mock_config_entry.minor_version,
        data=dict(mock_config_entry.data),
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    other_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(other_entry.entry_id)
    await hass.async_block_till_done()

    assert other_entry.state is ConfigEntryState.LOADED
    first, second = (
        (mock_config_entry, other_entry)
        if owner_first
        else (other_entry, mock_config_entry)
    )
    await hass.config_entries.async_unload(first.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, "system_bridge_hostname")
    second.runtime_data.websocket_client = AsyncMock()
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "system_bridge_hostname",
        {ATTR_MESSAGE: "World"},
        blocking=True,
    )
    second.runtime_data.websocket_client.send_notification.assert_awaited_once()

    await hass.config_entries.async_unload(second.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(NOTIFY_DOMAIN, "system_bridge_hostname")


@pytest.mark.usefixtures("mock_version", "mock_websocket_client")
async def test_legacy_notify_service_unloaded_during_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the legacy action isn't registered once its entry has unloaded."""
    discovery_info = {
        CONF_NAME: "system_bridge_hostname",
        CONF_ENTITY_ID: mock_config_entry.entry_id,
    }
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    service = await async_get_service(hass, {}, discovery_info)
    assert service is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await async_get_service(hass, {}, discovery_info) is None

    await service.async_setup(hass, "system_bridge_hostname", "system_bridge_hostname")
    await service.async_register_services()

    assert not hass.services.has_service(NOTIFY_DOMAIN, "system_bridge_hostname")
