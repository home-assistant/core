"""Tests for the System Bridge notify platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.notification import Notification

from homeassistant.components.notify import (
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

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def notify_only() -> Generator[None]:
    """Enable only the notify platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.NOTIFY],
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


@pytest.mark.usefixtures("mock_version")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_send_message_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
) -> None:
    """Test sending a message with exception."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_websocket_client.send_notification.side_effect = ConnectionClosedException

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
    assert e.value.translation_key == "send_message_failed"
    assert e.value.translation_placeholders == {
        "title": "TestSystem",
        "host": "127.0.0.1",
    }
