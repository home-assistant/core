"""Tests for the NRGkick switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, call

from nrgkick_api import NRGkickCommandRejectedError
from nrgkick_api.const import CONTROL_KEY_CHARGE_PAUSE
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_switch_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch entities."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.SWITCH])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_charge_switch_service_calls_update_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test the charge switch calls the API and updates state."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.SWITCH])

    entity_id = "switch.nrgkick_test_charging_enabled"

    assert (state := hass.states.get(entity_id))
    assert state.state == "on"

    # Pause charging
    # Simulate the device reporting the new paused state after the command.
    control_data = mock_nrgkick_api.get_control.return_value.copy()
    control_data[CONTROL_KEY_CHARGE_PAUSE] = 1
    mock_nrgkick_api.get_control.return_value = control_data
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == "off"

    # Resume charging
    # Simulate the device reporting the resumed state after the command.
    control_data = mock_nrgkick_api.get_control.return_value.copy()
    control_data[CONTROL_KEY_CHARGE_PAUSE] = 0
    mock_nrgkick_api.get_control.return_value = control_data
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == "on"

    assert mock_nrgkick_api.set_charge_pause.await_args_list == [
        call(True),
        call(False),
    ]


async def test_charge_switch_rejected_by_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test the switch surfaces device rejection messages and keeps state."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.SWITCH])

    entity_id = "switch.nrgkick_test_charging_enabled"

    # Device refuses the command and the library raises an exception.
    mock_nrgkick_api.set_charge_pause.side_effect = NRGkickCommandRejectedError(
        "Charging pause is blocked by solar-charging"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert err.value.translation_key == "command_rejected"
    assert err.value.translation_placeholders == {
        "reason": "Charging pause is blocked by solar-charging"
    }

    # State should reflect actual device control data (still not paused).
    assert (state := hass.states.get(entity_id))
    assert state.state == "on"
