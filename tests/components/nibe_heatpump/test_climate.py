"""Test the Nibe Heat Pump config flow."""
from typing import Any
from unittest.mock import patch

from nibe.coil_groups import CLIMATE_COILGROUPS, UNIT_COILGROUPS
from nibe.heatpump import Model
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import MockConnection, async_add_model


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch("homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.mark.parametrize(
    ("model", "climate_id", "entity_id"),
    [
        (Model.S320, "s1", "climate.climate_system_s1"),
    ],
)
async def test_basic(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    model: Model,
    climate_id: str,
    entity_id: str,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting of value."""
    climate = CLIMATE_COILGROUPS[model.series][climate_id]
    unit = UNIT_COILGROUPS[model.series]["main"]
    if climate.active_accessory is not None:
        coils[climate.active_accessory] = "ON"
    coils[climate.current] = 20.5
    coils[climate.setpoint_heat] = 21.0
    coils[climate.setpoint_cool] = 30.0
    coils[climate.mixing_valve_state] = "ON"
    coils[climate.use_room_sensor] = "ON"
    coils[unit.prio] = "HEAT"
    coils[unit.cooling_with_room_sensor] = "ON"

    await async_add_model(hass, model)

    assert hass.states.get(entity_id) == snapshot(name="1. initial")

    mock_connection.mock_coil_update(unit.prio, "OFF")

    assert hass.states.get(entity_id) == snapshot(name="2. idle")
