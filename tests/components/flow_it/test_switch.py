"""Test Flow-it switch platform."""

from unittest.mock import AsyncMock

from flow_it_api.exceptions import FlowItAuthError, FlowItCommandError, FlowItError
import pytest

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

AIR_INTAKE_ENTITY_ID = "switch.001122334455_air_intake"
AIR_EXHAUST_ENTITY_ID = "switch.001122334455_air_exhaust"


async def test_switch_setup(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch platform setup and entity registry."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state_in = hass.states.get(AIR_INTAKE_ENTITY_ID)
    assert state_in
    assert state_in.state == STATE_ON

    entry_in = entity_registry.async_get(AIR_INTAKE_ENTITY_ID)
    assert entry_in
    assert entry_in.unique_id == "001122334455_flow_in"
    assert entry_in.translation_key == "flow_in"

    state_out = hass.states.get(AIR_EXHAUST_ENTITY_ID)
    assert state_out
    assert state_out.state == STATE_ON

    entry_out = entity_registry.async_get(AIR_EXHAUST_ENTITY_ID)
    assert entry_out
    assert entry_out.unique_id == "001122334455_flow_out"
    assert entry_out.translation_key == "flow_out"


@pytest.mark.parametrize(
    ("entity_id", "service", "expected_flow_in", "expected_flow_out"),
    [
        (AIR_INTAKE_ENTITY_ID, SERVICE_TURN_ON, True, True),
        (AIR_INTAKE_ENTITY_ID, SERVICE_TURN_OFF, False, True),
        (AIR_EXHAUST_ENTITY_ID, SERVICE_TURN_ON, True, True),
        (AIR_EXHAUST_ENTITY_ID, SERVICE_TURN_OFF, True, False),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    service: str,
    expected_flow_in: bool,
    expected_flow_out: bool,
) -> None:
    """Test turning on and off the switches."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_flow_it.return_value.send_command.assert_awaited_once_with(
        "2",
        flow_in=expected_flow_in,
        flow_out=expected_flow_out,
    )


@pytest.mark.parametrize(
    ("exception", "expected_exception"),
    [
        (FlowItAuthError("Auth error"), ConfigEntryAuthFailed),
        (FlowItCommandError("Command error"), HomeAssistantError),
        (FlowItError("Generic error"), HomeAssistantError),
    ],
)
async def test_switch_exceptions(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_exception: type[Exception],
) -> None:
    """Test exception handling during switch commands."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_flow_it.return_value.send_command.side_effect = exception

    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: AIR_INTAKE_ENTITY_ID},
            blocking=True,
        )
