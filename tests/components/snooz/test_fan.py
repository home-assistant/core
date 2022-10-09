"""Test Snooz fan entity."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock, patch

from pysnooz.api import SnoozDeviceState, UnknownSnoozState
from pysnooz.commands import SnoozCommandResult, SnoozCommandResultStatus
from pysnooz.testing import MockSnoozDevice
import pytest

from homeassistant.components import fan
from homeassistant.components.snooz.const import DOMAIN
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry

from . import SnoozFixture, create_mock_snooz, create_mock_snooz_config_entry


async def test_turn_on(hass: HomeAssistant, snooz_fan_entity_id: str):
    """Test turning on the device."""
    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan_entity_id]},
        blocking=True,
    )

    state = hass.states.get(snooz_fan_entity_id)
    assert state.state == STATE_ON
    assert ATTR_ASSUMED_STATE not in state.attributes


@pytest.mark.parametrize("percentage", [1, 22, 50, 99, 100])
async def test_turn_on_with_percentage(
    hass: HomeAssistant, snooz_fan_entity_id: str, percentage: int
):
    """Test turning on the device with a percentage."""
    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan_entity_id], fan.ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    state = hass.states.get(snooz_fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == percentage
    assert ATTR_ASSUMED_STATE not in state.attributes


@pytest.mark.parametrize("percentage", [1, 22, 50, 99, 100])
async def test_set_percentage(
    hass: HomeAssistant, snooz_fan_entity_id: str, percentage: int
):
    """Test setting the fan percentage."""
    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: [snooz_fan_entity_id], fan.ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    state = hass.states.get(snooz_fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == percentage
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_set_0_percentage_turns_off(
    hass: HomeAssistant, snooz_fan_entity_id: str
):
    """Test turning off the device by setting the percentage/volume to 0."""
    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [snooz_fan_entity_id], fan.ATTR_PERCENTAGE: 66},
        blocking=True,
    )

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: [snooz_fan_entity_id], fan.ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    state = hass.states.get(snooz_fan_entity_id)
    assert state.state == STATE_OFF
    # doesn't overwrite percentage when turning off
    assert state.attributes[fan.ATTR_PERCENTAGE] == 66
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_turn_off(hass: HomeAssistant, snooz_fan_entity_id: str):
    """Test turning off the device."""
    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [snooz_fan_entity_id]},
        blocking=True,
    )

    state = hass.states.get(snooz_fan_entity_id)
    assert state.state == STATE_OFF
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_push_events(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture, snooz_fan_entity_id: str
):
    """Test state update events from snooz device."""
    mock_connected_snooz.device.trigger_state(SnoozDeviceState(False, 64))

    state = hass.states.get(snooz_fan_entity_id)
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PERCENTAGE] == 64

    mock_connected_snooz.device.trigger_state(SnoozDeviceState(True, 12))

    state = hass.states.get(snooz_fan_entity_id)
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 12

    mock_connected_snooz.device.trigger_disconnect()

    state = hass.states.get(snooz_fan_entity_id)
    assert state.attributes[ATTR_ASSUMED_STATE] is True


@pytest.mark.parametrize(
    "fan_state,percentage",
    [
        (STATE_OFF, 1),
        (STATE_OFF, 22),
        (STATE_OFF, 50),
        (STATE_OFF, 99),
        (STATE_OFF, 100),
        (STATE_ON, 1),
        (STATE_ON, 22),
        (STATE_ON, 50),
        (STATE_ON, 99),
        (STATE_ON, 100),
    ],
)
async def test_restore_state(hass: HomeAssistant, fan_state: str, percentage: int):
    """Tests restoring entity state."""
    disconnected_device = await create_mock_snooz(
        connected=False, initial_state=UnknownSnoozState
    )
    restored_state = State(
        "fan.test_restored", fan_state, {fan.ATTR_PERCENTAGE: percentage}
    )

    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=restored_state,
    ):
        await create_mock_snooz_config_entry(hass, disconnected_device)

        entity_id = get_fan_entity_id(hass, disconnected_device)

        state = hass.states.get(entity_id)
        assert state.state == fan_state
        assert state.attributes[fan.ATTR_PERCENTAGE] == percentage
        assert state.attributes[ATTR_ASSUMED_STATE] is True


async def test_restore_unknown_state(hass: HomeAssistant):
    """Tests restoring unknown entity state."""
    disconnected_device = await create_mock_snooz(
        connected=False, initial_state=UnknownSnoozState
    )
    restored_state = State("fan.test_restored", STATE_UNKNOWN)

    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=restored_state,
    ):
        await create_mock_snooz_config_entry(hass, disconnected_device)

        entity_id = get_fan_entity_id(hass, disconnected_device)

        state = hass.states.get(entity_id)
        assert state.state == STATE_UNKNOWN
        assert state.attributes[ATTR_ASSUMED_STATE] is True


async def test_command_results(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture, snooz_fan_entity_id: str
):
    """Test device command results."""
    with patch(
        "homeassistant.components.snooz.fan.SnoozFan._async_write_state_changed",
        autospec=True,
    ) as mock_write_state:
        mock_execute = Mock(spec=mock_connected_snooz.device.async_execute_command)

        mock_connected_snooz.device.async_execute_command = mock_execute

        mock_execute.return_value = SnoozCommandResult(
            SnoozCommandResultStatus.SUCCESSFUL, timedelta()
        )

        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [snooz_fan_entity_id]},
            blocking=True,
        )

        mock_write_state.assert_called_once()
        mock_write_state.reset_mock()

        mock_execute.return_value = SnoozCommandResult(
            SnoozCommandResultStatus.CANCELLED, timedelta()
        )

        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [snooz_fan_entity_id]},
            blocking=True,
        )

        mock_write_state.assert_not_called()

        mock_execute.return_value = SnoozCommandResult(
            SnoozCommandResultStatus.UNEXPECTED_ERROR, timedelta()
        )

        with pytest.raises(HomeAssistantError) as failure:
            await hass.services.async_call(
                fan.DOMAIN,
                fan.SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: [snooz_fan_entity_id]},
                blocking=True,
            )

        mock_write_state.assert_not_called()
        assert failure.match("failed with status")


@pytest.fixture(name="snooz_fan_entity_id")
async def fixture_snooz_fan_entity_id(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture
) -> str:
    """Mock a Snooz fan entity and config entry."""

    yield get_fan_entity_id(hass, mock_connected_snooz.device)


def get_fan_entity_id(hass: HomeAssistant, device: MockSnoozDevice) -> str:
    """Get the entity ID for a mock device."""

    return entity_registry.async_get(hass).async_get_entity_id(
        Platform.FAN, DOMAIN, device.address
    )
