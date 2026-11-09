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
