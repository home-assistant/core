"""Tests for the Infrared integration setup."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.infrared import (
    DATA_COMPONENT,
    DOMAIN,
    InfraredEntityFeature,
    NECInfraredCommand,
    async_get_entities,
    async_send_command,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MockInfraredEntity

from tests.common import mock_restore_cache


async def test_setup(hass: HomeAssistant) -> None:
    """Test Infrared integration setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Verify the component is loaded
    assert DATA_COMPONENT in hass.data


async def test_get_entities_empty(hass: HomeAssistant) -> None:
    """Test getting entities when none are registered."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    entities = async_get_entities(
        hass, supported_features=InfraredEntityFeature.TRANSMIT
    )
    assert entities == []


async def test_get_entities_filter_by_feature(
    hass: HomeAssistant,
    init_integration: None,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test filtering entities by feature support."""
    # Add the mock entity to the component
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    # Get entities with TRANSMIT feature (should match)
    transmit_entities = async_get_entities(
        hass, supported_features=InfraredEntityFeature.TRANSMIT
    )
    assert len(transmit_entities) == 1
    assert transmit_entities[0] is mock_infrared_entity

    # Get entities with RECEIVE feature (should not match since mock only supports TRANSMIT)
    receive_entities = async_get_entities(
        hass, supported_features=InfraredEntityFeature.RECEIVE
    )
    assert len(receive_entities) == 0


async def test_infrared_entity_initial_state(
    hass: HomeAssistant,
    init_integration: None,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test infrared entity has no state before any command is sent."""
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    state = hass.states.get("infrared.test_ir_transmitter")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_infrared_entity_send_command(
    hass: HomeAssistant,
    init_integration: None,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test sending command via infrared entity."""
    # Add the mock entity to the component
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    # Create a test command
    command = NECInfraredCommand(
        address=0x04FB,
        command=0x08F7,
        repeat_count=1,
    )

    # Send command
    await mock_infrared_entity.async_send_command(command)

    # Verify command was recorded
    assert len(mock_infrared_entity.send_command_calls) == 1
    assert mock_infrared_entity.send_command_calls[0] is command


async def test_infrared_entity_features(
    hass: HomeAssistant,
    init_integration: None,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test infrared entity features property."""
    assert mock_infrared_entity.supported_features == InfraredEntityFeature.TRANSMIT


async def test_async_send_command_success(
    hass: HomeAssistant,
    init_integration: None,
    mock_infrared_entity: MockInfraredEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sending command via async_send_command helper."""
    # Add the mock entity to the component
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    # Freeze time
    now = dt_util.utcnow()
    freezer.move_to(now)

    command = NECInfraredCommand(address=0x04FB, command=0x08F7, repeat_count=1)
    await async_send_command(hass, "infrared.test_ir_transmitter", command)

    assert len(mock_infrared_entity.send_command_calls) == 1
    assert mock_infrared_entity.send_command_calls[0] is command

    state = hass.states.get("infrared.test_ir_transmitter")
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")


async def test_async_send_command_entity_not_found(
    hass: HomeAssistant, init_integration: None
) -> None:
    """Test async_send_command raises error when entity not found."""
    command = NECInfraredCommand(address=0x04FB, command=0x08F7, repeat_count=1)

    with pytest.raises(
        HomeAssistantError,
        match="Infrared entity `infrared.nonexistent_entity` not found",
    ):
        await async_send_command(hass, "infrared.nonexistent_entity", command)


async def test_async_send_command_component_not_loaded(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when component not loaded."""
    command = NECInfraredCommand(address=0x04FB, command=0x08F7, repeat_count=1)

    with pytest.raises(HomeAssistantError, match="Infrared component not loaded"):
        await async_send_command(hass, "infrared.some_entity", command)


async def test_infrared_entity_state_restore(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test infrared entity restores state from previous session."""
    # Set up restore cache with a previous state (milliseconds format)
    previous_timestamp = "2026-01-01T12:00:00.000+00:00"
    mock_restore_cache(
        hass,
        [State("infrared.test_ir_transmitter", previous_timestamp)],
    )

    # Set up integration
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Add entity
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    # Verify state was restored
    state = hass.states.get("infrared.test_ir_transmitter")
    assert state is not None
    assert state.state == previous_timestamp
