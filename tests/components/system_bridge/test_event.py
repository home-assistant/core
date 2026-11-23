"""Tests for the System Bridge event platform."""

from collections.abc import Generator
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.models.fixtures.modules.system import FIXTURE_SYSTEM
from systembridgeconnector.models.notification import (
    NotificationButton,
    NotificationEvent,
)

from homeassistant.components.event import EventEntityStateAttribute
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "event.hostname_notification"


@pytest.fixture(autouse=True)
def event_only() -> Generator[None]:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.EVENT],
    ):
        yield


async def _setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    version: str,
) -> None:
    """Set up the integration with a backend of the given version."""
    system = replace(FIXTURE_SYSTEM, version=version)
    mock_websocket_client.get_data.return_value = replace(
        mock_websocket_client.get_data.return_value, system=system
    )
    mock_config_entry.add_to_hass(hass)
    # The mocked listener sends the system data again before the platforms load
    with patch("tests.components.system_bridge.FIXTURE_SYSTEM", system):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_version")
async def test_event_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the event platform."""
    await _setup(hass, mock_config_entry, mock_websocket_client, "5.20.0")

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_version")
async def test_no_event_entity_before_5_20(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
) -> None:
    """Test backends that don't report notification events get no event entity."""
    await _setup(hass, mock_config_entry, mock_websocket_client, "5.19.0")

    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.usefixtures("mock_version")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
@pytest.mark.parametrize(
    ("event", "event_type", "attributes"),
    [
        pytest.param(
            NotificationEvent(id=12, action="default"),
            "clicked",
            {"notification_id": 12, "action": "default"},
            id="clicked",
        ),
        pytest.param(
            NotificationEvent(id=12, action="yes"),
            "clicked",
            {"notification_id": 12, "action": "yes"},
            id="button",
        ),
        pytest.param(
            NotificationEvent(id=12, reason="expired"),
            "closed",
            {"notification_id": 12, "reason": "expired"},
            id="closed",
        ),
        pytest.param(
            NotificationEvent(
                id=12,
                title="Backup finished",
                message="All files were copied",
                buttons=[NotificationButton(id="open", label="Open")],
            ),
            "sent",
            {
                "notification_id": 12,
                "title": "Backup finished",
                "message": "All files were copied",
                "buttons": [{"id": "open", "label": "Open"}],
            },
            id="sent",
        ),
    ],
)
async def test_notification_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: AsyncMock,
    event: NotificationEvent,
    event_type: str,
    attributes: dict[str, Any],
) -> None:
    """Test a notification event from the WebSocket fires the event entity."""
    await _setup(hass, mock_config_entry, mock_websocket_client, "5.20.0")

    notification_event_callback = mock_websocket_client.listen.call_args.kwargs[
        "notification_event_callback"
    ]
    await notification_event_callback(event)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "2009-02-13T23:31:30.000+00:00"
    assert state.attributes[EventEntityStateAttribute.EVENT_TYPE] == event_type
    assert attributes.items() <= state.attributes.items()
