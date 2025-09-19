"""Tests for init module."""

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from aioautomower.model import MowerAttributes, SingleMessageData
from aioautomower.model.model_message import Message, Severity, SingleMessageAttributes
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.freeze_time(datetime(2023, 6, 5, 12))
async def test_event(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    values: dict[str, MowerAttributes],
    automower_ws_ready: list[Callable[[], None]],
) -> None:
    """Test that a new message arriving over the websocket creates and updates the sensor."""
    callbacks: list[Callable[[SingleMessageData], None]] = []

    @callback
    def fake_register_websocket_response(
        cb: Callable[[SingleMessageData], None],
    ) -> None:
        callbacks.append(cb)

    mock_automower_client.register_single_message_callback.side_effect = (
        fake_register_websocket_response
    )
    mock_automower_client.send_empty_message.return_value = True

    # Set up integration
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Start the watchdog and let it run once to set websocket_alive=True
    for cb in automower_ws_ready:
        cb()
    await hass.async_block_till_done()

    # Ensure callback was registered for the test mower
    assert mock_automower_client.register_single_message_callback.called

    # Check initial state (event entity not available yet)
    state = hass.states.get("event.test_mower_1_message")
    assert state is None

    # Simulate a new message for this mower and check entity creation
    message = SingleMessageData(
        type="messages",
        id=TEST_MOWER_ID,
        attributes=SingleMessageAttributes(
            message=Message(
                time=datetime(2025, 7, 13, 15, 30, tzinfo=UTC),
                code="wheel_motor_overloaded_rear_left",
                severity=Severity.ERROR,
                latitude=49.0,
                longitude=10.0,
            )
        ),
    )

    for cb in callbacks:
        cb(message)
    await hass.async_block_till_done()

    state = hass.states.get("event.test_mower_1_message")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "wheel_motor_overloaded_rear_left"

    # Reload the config entry to ensure the entity is created again
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Start the new watchdog and let it run
    for cb in automower_ws_ready:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get("event.test_mower_1_message")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "wheel_motor_overloaded_rear_left"

    # Check updating event with a new message
    message = SingleMessageData(
        type="messages",
        id=TEST_MOWER_ID,
        attributes=SingleMessageAttributes(
            message=Message(
                time=datetime(2025, 7, 13, 16, 00, tzinfo=UTC),
                code="alarm_mower_lifted",
                severity=Severity.ERROR,
                latitude=48.0,
                longitude=11.0,
            )
        ),
    )

    for cb in callbacks:
        cb(message)
    await hass.async_block_till_done()
    state = hass.states.get("event.test_mower_1_message")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "alarm_mower_lifted"

    # Check message for another mower, creates an new entity and dont
    # change the state of the first entity
    message = SingleMessageData(
        type="messages",
        id="1234",
        attributes=SingleMessageAttributes(
            message=Message(
                time=datetime(2025, 7, 13, 16, 00, tzinfo=UTC),
                code="battery_problem",
                severity=Severity.ERROR,
                latitude=48.0,
                longitude=11.0,
            )
        ),
    )

    for cb in callbacks:
        cb(message)
    await hass.async_block_till_done()

    entry = entity_registry.async_get("event.test_mower_1_message")
    assert entry is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "alarm_mower_lifted"
    state = hass.states.get("event.test_mower_2_message")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "battery_problem"

    # Check event entity is removed, when the mower is removed
    values_copy = deepcopy(values)
    values_copy.pop("1234")
    mock_automower_client.get_status.return_value = values_copy
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("event.test_mower_2_message")
    assert state is None
    entry = entity_registry.async_get("event.test_mower_2_message")
    assert entry is None


@pytest.mark.freeze_time(datetime(2023, 6, 5, 12))
async def test_event_snapshot(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    automower_ws_ready: list[Callable[[], None]],
) -> None:
    """Test that a new message arriving over the websocket updates the sensor."""
    with patch(
        "homeassistant.components.husqvarna_automower.PLATFORMS",
        [Platform.EVENT],
    ):
        callbacks: list[Callable[[SingleMessageData], None]] = []

        @callback
        def fake_register_websocket_response(
            cb: Callable[[SingleMessageData], None],
        ) -> None:
            callbacks.append(cb)

        mock_automower_client.register_single_message_callback.side_effect = (
            fake_register_websocket_response
        )

        # Set up integration
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

        # Start the watchdog and let it run once
        for cb in automower_ws_ready:
            cb()
        await hass.async_block_till_done()

        # Ensure callback was registered for the test mower
        assert mock_automower_client.register_single_message_callback.called

        # Simulate a new message for this mower
        message = SingleMessageData(
            type="messages",
            id=TEST_MOWER_ID,
            attributes=SingleMessageAttributes(
                message=Message(
                    time=datetime(2025, 7, 13, 15, 30, tzinfo=UTC),
                    code="wheel_motor_overloaded_rear_left",
                    severity=Severity.ERROR,
                    latitude=49.0,
                    longitude=10.0,
                )
            ),
        )

        for cb in callbacks:
            cb(message)
        await hass.async_block_till_done()

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
