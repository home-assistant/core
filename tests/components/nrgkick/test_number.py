"""Tests for the NRGkick number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from nrgkick_api import NRGkickCommandRejectedError
from nrgkick_api.const import (
    CONTROL_KEY_CURRENT_SET,
    CONTROL_KEY_ENERGY_LIMIT,
    CONTROL_KEY_PHASE_COUNT,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_number_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test number entities."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.NUMBER])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_charging_current(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test setting charging current calls the API and updates state."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.NUMBER])

    entity_id = "number.nrgkick_test_charging_current"

    assert (state := hass.states.get(entity_id))
    assert state.state == "16.0"

    # Set current to 10A
    control_data = mock_nrgkick_api.get_control.return_value.copy()
    control_data[CONTROL_KEY_CURRENT_SET] = 10.0
    mock_nrgkick_api.get_control.return_value = control_data
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 10.0},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == "10.0"

    mock_nrgkick_api.set_current.assert_awaited_once_with(10.0)


async def test_set_energy_limit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test setting energy limit calls the API and updates state."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.NUMBER])

    entity_id = "number.nrgkick_test_energy_limit"

    assert (state := hass.states.get(entity_id))
    assert state.state == "0"

    # Set energy limit to 5000 Wh
    control_data = mock_nrgkick_api.get_control.return_value.copy()
    control_data[CONTROL_KEY_ENERGY_LIMIT] = 5000
    mock_nrgkick_api.get_control.return_value = control_data
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 5000},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == "5000"

    mock_nrgkick_api.set_energy_limit.assert_awaited_once_with(5000)


async def test_set_phase_count(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test setting phase count calls the API and updates state."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.NUMBER])

    entity_id = "number.nrgkick_test_phase_count"

    assert (state := hass.states.get(entity_id))
    assert state.state == "3"

    # Set to 1 phase
    control_data = mock_nrgkick_api.get_control.return_value.copy()
    control_data[CONTROL_KEY_PHASE_COUNT] = 1
    mock_nrgkick_api.get_control.return_value = control_data
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 1},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id))
    assert state.state == "1"

    mock_nrgkick_api.set_phase_count.assert_awaited_once_with(1)


async def test_number_command_rejected_by_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test number entity surfaces device rejection messages."""
    await setup_integration(hass, mock_config_entry, platforms=[Platform.NUMBER])

    entity_id = "number.nrgkick_test_charging_current"

    mock_nrgkick_api.set_current.side_effect = NRGkickCommandRejectedError(
        "Current change blocked by solar-charging"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 10.0},
            blocking=True,
        )

    assert err.value.translation_key == "command_rejected"
    assert err.value.translation_placeholders == {
        "reason": "Current change blocked by solar-charging"
    }

    # State should reflect actual device control data (unchanged).
    assert (state := hass.states.get(entity_id))
    assert state.state == "16.0"


async def test_charging_current_max_limited_by_connector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test that the charging current max is limited by the connector."""
    # Device rated at 32A, but connector only supports 16A.
    mock_nrgkick_api.get_info.return_value["general"]["rated_current"] = 32.0
    mock_nrgkick_api.get_info.return_value["connector"]["max_current"] = 16.0

    await setup_integration(hass, mock_config_entry, platforms=[Platform.NUMBER])

    entity_id = "number.nrgkick_test_charging_current"

    assert (state := hass.states.get(entity_id))
    assert state.attributes["max"] == 16.0
