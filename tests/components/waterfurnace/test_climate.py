"""Test climate of WaterFurnace integration."""

from unittest.mock import Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.waterfurnace.const import UPDATE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "climate.test_abc_type"


@pytest.mark.usefixtures("mock_waterfurnace_client", "seed_statistics")
async def test_climate_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity against snapshot."""
    with patch("homeassistant.components.waterfurnace.PLATFORMS", [Platform.CLIMATE]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("seed_statistics", "init_integration")
async def test_set_hvac_mode_raises(
    hass: HomeAssistant,
) -> None:
    """Test that setting HVAC mode raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )


@pytest.mark.usefixtures("seed_statistics", "init_integration")
@pytest.mark.parametrize(
    ("active_mode_index", "expected_hvac_mode"),
    [
        (0, HVACMode.OFF),
        (1, HVACMode.AUTO),
        (2, HVACMode.COOL),
        (3, HVACMode.HEAT),
        (4, HVACMode.HEAT),
    ],
    ids=["Off", "Auto", "Cool", "Heat", "E-Heat"],
)
async def test_hvac_mode_mapping(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    active_mode_index: int,
    expected_hvac_mode: HVACMode,
) -> None:
    """Test that ActiveSettings.mode maps to the correct HVACMode."""
    mock_waterfurnace_client.read_with_retry.return_value.activesettings.activemode = (
        active_mode_index
    )
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == expected_hvac_mode.value


@pytest.mark.usefixtures("seed_statistics", "init_integration")
@pytest.mark.parametrize(
    ("mode_index", "expected_action"),
    [
        (0, HVACAction.IDLE),
        (1, HVACAction.FAN),
        (2, HVACAction.COOLING),
        (3, HVACAction.COOLING),
        (4, HVACAction.HEATING),
        (5, HVACAction.HEATING),
        (6, HVACAction.HEATING),
        (7, HVACAction.HEATING),
        (8, HVACAction.HEATING),
        (9, HVACAction.OFF),
    ],
    ids=[
        "Standby",
        "Fan Only",
        "Cooling 1",
        "Cooling 2",
        "Reheat",
        "Heating 1",
        "Heating 2",
        "E-Heat",
        "Aux Heat",
        "Lockout",
    ],
)
async def test_hvac_action_mapping(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mode_index: int,
    expected_action: HVACAction,
) -> None:
    """Test that WFReading.mode maps to the correct HVACAction."""
    mock_waterfurnace_client.read_with_retry.return_value.modeofoperation = mode_index
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes["hvac_action"] == expected_action
