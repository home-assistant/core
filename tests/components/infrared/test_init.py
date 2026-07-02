"""Tests for the Infrared integration setup."""

import re
from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components.infrared import (
    DATA_COMPONENT,
    DOMAIN,
    InfraredReceivedSignal,
    async_get_emitters,
    async_get_receivers,
    async_send_command,
    async_subscribe_receiver,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import MockInfraredEmitterEntity, MockInfraredReceiverEntity

from tests.common import mock_restore_cache

TEST_COMMAND = NECCommand(address=0x04FB, command=0x08F7, modulation=38000)


async def test_get_entities_component_not_loaded(hass: HomeAssistant) -> None:
    """Test getting entities when the component is not loaded."""
    assert async_get_emitters(hass) == []
    assert async_get_receivers(hass) == []


@pytest.mark.usefixtures("init_infrared")
async def test_get_entities_empty(hass: HomeAssistant) -> None:
    """Test getting entities when none are registered."""
    assert async_get_emitters(hass) == []
    assert async_get_receivers(hass) == []


async def test_get_entities_filters_by_type(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test get_emitters/get_receivers return only entities of the matching type."""
    assert async_get_emitters(hass) == [mock_infrared_emitter_entity.entity_id]
    assert async_get_receivers(hass) == [mock_infrared_receiver_entity.entity_id]


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_infrared_entities_initial_state(hass: HomeAssistant) -> None:
    """Test infrared entities have no state before any command is sent."""
    assert (emitter_state := hass.states.get("infrared.test_ir_emitter")) is not None
    assert emitter_state.state == STATE_UNKNOWN
    assert (receiver_state := hass.states.get("infrared.test_ir_receiver")) is not None
    assert receiver_state.state == STATE_UNKNOWN


async def test_async_send_command_success(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sending command via async_send_command helper."""
    now = dt_util.utcnow()
    freezer.move_to(now)

    await async_send_command(hass, mock_infrared_emitter_entity.entity_id, TEST_COMMAND)

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0] is TEST_COMMAND

    state = hass.states.get("infrared.test_ir_emitter")
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")


async def test_async_send_command_error_does_not_update_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test that state is not updated when async_send_command raises an error."""
    state = hass.states.get("infrared.test_ir_emitter")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    mock_infrared_emitter_entity.async_send_command = AsyncMock(
        side_effect=HomeAssistantError("Transmission failed")
    )

    with pytest.raises(HomeAssistantError, match="Transmission failed"):
        await async_send_command(
            hass, mock_infrared_emitter_entity.entity_id, TEST_COMMAND
        )

    state = hass.states.get("infrared.test_ir_emitter")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_infrared")
async def test_async_send_command_entity_not_found(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when entity not found."""
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Infrared entity `infrared.nonexistent_entity` not found"),
    ):
        await async_send_command(hass, "infrared.nonexistent_entity", TEST_COMMAND)


async def test_async_send_command_rejects_receiver(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test async_send_command rejects a receiver entity."""
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Infrared entity `{mock_infrared_receiver_entity.entity_id}` not found"
        ),
    ):
        await async_send_command(
            hass, mock_infrared_receiver_entity.entity_id, TEST_COMMAND
        )


async def test_async_send_command_component_not_loaded(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when component not loaded."""
    with pytest.raises(HomeAssistantError, match="component_not_loaded"):
        await async_send_command(hass, "infrared.some_entity", TEST_COMMAND)


@pytest.mark.parametrize(
    ("restored_value", "expected_state"),
    [
        ("2026-01-01T12:00:00.000+00:00", "2026-01-01T12:00:00.000+00:00"),
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
    ],
)
async def test_infrared_entity_state_restore(
    hass: HomeAssistant, restored_value: str, expected_state: str
) -> None:
    """Test infrared entity state restore."""
    mock_restore_cache(
        hass,
        [
            State("infrared.test_ir_emitter", restored_value),
            State("infrared.test_ir_receiver", restored_value),
        ],
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities(
        [
            MockInfraredEmitterEntity("test_ir_emitter"),
            MockInfraredReceiverEntity("test_ir_receiver"),
        ]
    )

    assert (emitter_state := hass.states.get("infrared.test_ir_emitter")) is not None
    assert emitter_state.state == expected_state
    assert (receiver_state := hass.states.get("infrared.test_ir_receiver")) is not None
    assert receiver_state.state == expected_state


async def test_async_subscribe_receiver_success(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test subscribing to a receiver via async_subscribe_receiver helper."""
    now = dt_util.utcnow()
    freezer.move_to(now)

    signal_callback = Mock()
    unsubscribe = async_subscribe_receiver(
        hass, mock_infrared_receiver_entity.entity_id, signal_callback
    )

    signal = InfraredReceivedSignal(timings=[100, 200, 300], modulation=38000)
    mock_infrared_receiver_entity._handle_received_signal(signal)

    assert signal_callback.call_count == 1
    assert signal_callback.call_args[0][0] is signal

    state = hass.states.get("infrared.test_ir_receiver")
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")

    unsubscribe()
    mock_infrared_receiver_entity._handle_received_signal(signal)
    assert signal_callback.call_count == 1


async def test_handle_received_signal_isolates_callback_errors(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing subscriber does not prevent other subscribers from running."""
    failing_callback = Mock(side_effect=RuntimeError("boom"))
    working_callback = Mock()
    async_subscribe_receiver(
        hass, mock_infrared_receiver_entity.entity_id, failing_callback
    )
    async_subscribe_receiver(
        hass, mock_infrared_receiver_entity.entity_id, working_callback
    )

    signal = InfraredReceivedSignal(timings=[100, 200, 300])
    mock_infrared_receiver_entity._handle_received_signal(signal)

    failing_callback.assert_called_once_with(signal)
    working_callback.assert_called_once_with(signal)
    assert "Error in signal callback" in caplog.text


async def test_handle_received_signal_unsubscribe_during_dispatch(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a subscriber can unsubscribe itself during dispatch without error."""
    other_callback = Mock()

    def unsubscribing_callback(signal: InfraredReceivedSignal) -> None:
        unsubscribe()

    self_unsub_mock = Mock(side_effect=unsubscribing_callback)
    unsubscribe = async_subscribe_receiver(
        hass, mock_infrared_receiver_entity.entity_id, self_unsub_mock
    )
    async_subscribe_receiver(
        hass, mock_infrared_receiver_entity.entity_id, other_callback
    )

    signal = InfraredReceivedSignal(timings=[100, 200, 300])
    mock_infrared_receiver_entity._handle_received_signal(signal)

    self_unsub_mock.assert_called_once_with(signal)
    other_callback.assert_called_once_with(signal)

    mock_infrared_receiver_entity._handle_received_signal(signal)
    self_unsub_mock.assert_called_once_with(signal)
    assert other_callback.call_count == 2


@pytest.mark.usefixtures("init_infrared")
@pytest.mark.parametrize(
    "entity_id_or_uuid",
    ["infrared.nonexistent_entity", "invalid-id"],
)
async def test_async_subscribe_receiver_not_found(
    hass: HomeAssistant, entity_id_or_uuid: str
) -> None:
    """Test async_subscribe_receiver raises when the entity is missing or invalid."""
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(f"Infrared receiver entity `{entity_id_or_uuid}` not found"),
    ):
        async_subscribe_receiver(hass, entity_id_or_uuid, lambda _: None)


async def test_async_subscribe_receiver_rejects_emitter(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test async_subscribe_receiver rejects an emitter entity."""
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Infrared receiver entity `{mock_infrared_emitter_entity.entity_id}`"
            " not found"
        ),
    ):
        async_subscribe_receiver(
            hass, mock_infrared_emitter_entity.entity_id, lambda _: None
        )


async def test_async_subscribe_receiver_component_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Test async_subscribe_receiver raises error when component not loaded."""
    with pytest.raises(HomeAssistantError, match="component_not_loaded"):
        async_subscribe_receiver(hass, "infrared.some_entity", lambda _: None)
