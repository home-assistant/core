"""Tests for init module."""

from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from aioautomower.exceptions import ApiError
from aioautomower.model import MessageData
from aioautomower.model.model_message import Message, MessageAttributes, Severity
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_event(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a new message arriving over the websocket updates the sensor."""
    original_side_effect = mock_automower_client.async_get_messages.side_effect
    mock_automower_client.async_get_messages.side_effect = ApiError
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()
    state = hass.states.get("event.test_mower_1_last_error")
    assert state is None

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    mock_automower_client.async_get_messages.side_effect = original_side_effect
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()
    state = hass.states.get("event.test_mower_1_last_error")
    assert state is not None


@pytest.mark.freeze_time(datetime(2023, 6, 5, 12))
async def test_new_websocket_message(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a new message arriving over the websocket updates the sensor."""
    with patch(
        "homeassistant.components.husqvarna_automower.PLATFORMS",
        [Platform.EVENT],
    ):
        # Capture callbacks per mower_id
        callback_holder: dict[str, Callable[[MessageData], None]] = {}

        @callback
        def fake_register_websocket_response(
            cb: Callable[[MessageData], None],
            mower_id: str,
        ) -> None:
            callback_holder[mower_id] = cb

        mock_automower_client.register_message_callback.side_effect = (
            fake_register_websocket_response
        )

        # Set up integration
        await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Wait for all coordinator/entity setup
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Ensure callback was registered for the test mower
    assert mock_automower_client.register_message_callback.called
    assert TEST_MOWER_ID in callback_holder

    # Check initial state
    state = hass.states.get("event.test_mower_1_last_error")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Simulate a new message for this mower
    message = MessageData(
        type="messages",
        id=TEST_MOWER_ID,
        attributes=MessageAttributes(
            messages=[
                Message(
                    time=datetime(2025, 7, 13, 15, 30, tzinfo=UTC),
                    code="wheel_motor_overloaded_rear_left",
                    severity=Severity.ERROR,
                    latitude=49.0,
                    longitude=10.0,
                )
            ]
        ),
    )
    callback_holder[TEST_MOWER_ID](message)
    await hass.async_block_till_done()
    freezer.tick(SCAN_INTERVAL)
    await hass.async_block_till_done()
    state = hass.states.get("event.test_mower_1_last_error")
    assert state.attributes[ATTR_EVENT_TYPE] == "wheel_motor_overloaded_rear_left"
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
