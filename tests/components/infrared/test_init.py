"""Tests for the Infrared integration setup."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from infrared_protocols import NECCommand
import pytest

from homeassistant.components.infrared import (
    DATA_COMPONENT,
    DOMAIN,
    async_get_emitters,
    async_send_command,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MockInfraredEntity

from tests.common import mock_restore_cache


async def test_get_entities_integration_setup(hass: HomeAssistant) -> None:
    """Test getting entities when the integration is not setup."""
    assert async_get_emitters(hass) == []


@pytest.mark.usefixtures("init_integration")
async def test_get_entities_empty(hass: HomeAssistant) -> None:
    """Test getting entities when none are registered."""
    assert async_get_emitters(hass) == []


@pytest.mark.usefixtures("init_integration")
async def test_infrared_entity_initial_state(
    hass: HomeAssistant, mock_infrared_entity: MockInfraredEntity
) -> None:
    """Test infrared entity has no state before any command is sent."""
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    state = hass.states.get("infrared.test_ir_transmitter")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_async_send_command_success(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sending command via async_send_command helper."""
    # Add the mock entity to the component
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    # Freeze time so we can verify the state update
    now = dt_util.utcnow()
    freezer.move_to(now)

    command = NECCommand(address=0x04FB, command=0x08F7, modulation=38000)
    await async_send_command(hass, mock_infrared_entity.entity_id, command)

    assert len(mock_infrared_entity.send_command_calls) == 1
    assert mock_infrared_entity.send_command_calls[0] is command

    state = hass.states.get("infrared.test_ir_transmitter")
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")


@pytest.mark.usefixtures("init_integration")
async def test_async_send_command_error_does_not_update_state(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test that state is not updated when async_send_command raises an error."""
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    state = hass.states.get("infrared.test_ir_transmitter")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    command = NECCommand(address=0x04FB, command=0x08F7, modulation=38000)

    mock_infrared_entity.async_send_command = AsyncMock(
        side_effect=HomeAssistantError("Transmission failed")
    )

    with pytest.raises(HomeAssistantError, match="Transmission failed"):
        await async_send_command(hass, mock_infrared_entity.entity_id, command)

    # Verify state was not updated after the error
    state = hass.states.get("infrared.test_ir_transmitter")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_async_send_command_entity_not_found(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when entity not found."""
    command = NECCommand(
        address=0x04FB, command=0x08F7, modulation=38000, repeat_count=1
    )

    with pytest.raises(
        HomeAssistantError,
        match="Infrared entity `infrared.nonexistent_entity` not found",
    ):
        await async_send_command(hass, "infrared.nonexistent_entity", command)


async def test_async_send_command_component_not_loaded(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when component not loaded."""
    command = NECCommand(
        address=0x04FB, command=0x08F7, modulation=38000, repeat_count=1
    )

    with pytest.raises(HomeAssistantError, match="component_not_loaded"):
        await async_send_command(hass, "infrared.some_entity", command)


@pytest.mark.parametrize(
    ("restored_value", "expected_state"),
    [
        ("2026-01-01T12:00:00.000+00:00", "2026-01-01T12:00:00.000+00:00"),
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
    ],
)
async def test_infrared_entity_state_restore(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
    restored_value: str,
    expected_state: str,
) -> None:
    """Test infrared entity state restore."""
    mock_restore_cache(hass, [State("infrared.test_ir_transmitter", restored_value)])

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    state = hass.states.get("infrared.test_ir_transmitter")
    assert state is not None
    assert state.state == expected_state
