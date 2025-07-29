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
from homeassistant.components.husqvarna_automower.event import STORAGE_KEY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def get_seen_mowers(hass: HomeAssistant) -> dict[str, bool]:
    """Return the current seen mowers from persistent storage."""
    store = Store(hass, 1, STORAGE_KEY)
    return await store.async_load() or {}


@pytest.mark.freeze_time(datetime(2023, 6, 5, 12))
async def test_event(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    values: dict[str, MowerAttributes],
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

    # Set up integration
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Ensure callback was registered for the test mower
    assert mock_automower_client.register_single_message_callback.called

    # Check initial state
    state = hass.states.get("event.test_mower_1_message")
    assert state is None

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
    state = hass.states.get("event.test_mower_1_message")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "wheel_motor_overloaded_rear_left"

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.test_mower_1_message")
    assert state.attributes[ATTR_EVENT_TYPE] == "wheel_motor_overloaded_rear_left"
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
    state = hass.states.get("event.test_mower_1_message")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "alarm_mower_lifted"

    state = hass.states.get("event.test_mower_2_message")
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "battery_problem"
    seen_mowers = await get_seen_mowers(hass)
    assert "1234" in seen_mowers

    values_copy = deepcopy(values)
    values_copy.pop("1234")
    mock_automower_client.get_status.return_value = values_copy
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("event.test_mower_2_message")
    assert state is None
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()
    state = hass.states.get("event.test_mower_2_message")
    assert state is None

    seen_mowers = await get_seen_mowers(hass)
    assert "1234" not in seen_mowers


@pytest.mark.freeze_time(datetime(2023, 6, 5, 12))
async def test_event_snapshot(
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
