"""Tests for the BSB-LAN number platform."""

from typing import Any
from unittest.mock import AsyncMock

from bsblan import BSBLANError, SetHotWaterParam, StaticState
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

COMFORT_ENTITY_ID = "number.heating_circuit_1_comfort_temperature"
REDUCED_ENTITY_ID = "number.heating_circuit_1_reduced_temperature"
NOMINAL_ENTITY_ID = "number.water_heater_nominal_temperature"
DHW_REDUCED_ENTITY_ID = "number.water_heater_reduced_temperature"


def _temp_param(value: str) -> dict[str, Any]:
    """Build a raw BSB-LAN temperature parameter payload."""
    return {
        "name": "",
        "value": value,
        "unit": "&deg;C",
        "desc": "",
        "dataType": 0,
        "readonly": 0,
        "error": 0,
    }


@pytest.fixture(autouse=True)
def mock_static_values(mock_bsblan: AsyncMock) -> None:
    """Mock the circuit config with a reduced setpoint of 17.0."""
    mock_bsblan.static_values.return_value = StaticState.model_validate(
        {
            "temp_reduced_setpoint": _temp_param("17.0"),
            "heating_protective_setpoint": _temp_param("8.0"),
            "comfort_setpoint_max": _temp_param("26.0"),
        }
    )


async def _async_set_value(hass: HomeAssistant, entity_id: str, value: float) -> None:
    """Set the value of a number entity."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )


async def test_number_entities(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the number entities."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_number_entities_not_available(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no setpoints are created when the device does not expose them."""
    mock_bsblan.state.return_value.target_temperature = None
    mock_bsblan.static_values.return_value = StaticState.model_validate({})
    mock_bsblan.hot_water_state.return_value.nominal_setpoint = None

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    assert hass.states.async_entity_ids(NUMBER_DOMAIN) == []


@pytest.mark.parametrize(
    ("entity_id", "value", "expected_call"),
    [
        (COMFORT_ENTITY_ID, 19.5, {"target_temperature": 19.5}),
        (REDUCED_ENTITY_ID, 16.5, {"temp_reduced_setpoint": 16.5}),
    ],
)
async def test_set_circuit_setpoint(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    value: float,
    expected_call: dict[str, float],
) -> None:
    """Test setting a heating circuit setpoint."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    await _async_set_value(hass, entity_id, value)

    mock_bsblan.thermostat.assert_called_once_with(**expected_call, circuit=1)


@pytest.mark.parametrize(
    ("entity_id", "value", "expected_param"),
    [
        (NOMINAL_ENTITY_ID, 55, SetHotWaterParam(nominal_setpoint=55)),
        (DHW_REDUCED_ENTITY_ID, 30, SetHotWaterParam(reduced_setpoint=30)),
    ],
)
async def test_set_hot_water_setpoint(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    value: float,
    expected_param: SetHotWaterParam,
) -> None:
    """Test setting a hot water setpoint."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    await _async_set_value(hass, entity_id, value)

    mock_bsblan.set_hot_water.assert_called_once_with(expected_param)


@pytest.mark.parametrize(
    ("entity_id", "value", "translation_key"),
    [
        (COMFORT_ENTITY_ID, 16.5, "comfort_below_reduced"),
        (REDUCED_ENTITY_ID, 19.0, "reduced_above_comfort"),
        (NOMINAL_ENTITY_ID, 30, "nominal_below_reduced"),
        (DHW_REDUCED_ENTITY_ID, 55, "reduced_above_nominal"),
    ],
)
async def test_set_setpoint_rejects_order(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    value: float,
    translation_key: str,
) -> None:
    """Test a reduced setpoint cannot end up above its comfort or nominal one."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    with pytest.raises(ServiceValidationError) as exc:
        await _async_set_value(hass, entity_id, value)

    assert exc.value.translation_key == translation_key
    mock_bsblan.thermostat.assert_not_called()
    mock_bsblan.set_hot_water.assert_not_called()


@pytest.mark.parametrize(
    ("entity_id", "value", "method", "translation_key"),
    [
        (COMFORT_ENTITY_ID, 20, "thermostat", "set_data_error"),
        (NOMINAL_ENTITY_ID, 55, "set_hot_water", "set_temperature_error"),
    ],
)
async def test_set_setpoint_error(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    value: float,
    method: str,
    translation_key: str,
) -> None:
    """Test a failed write raises an error."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])
    getattr(mock_bsblan, method).side_effect = BSBLANError("Test error")

    with pytest.raises(HomeAssistantError) as exc:
        await _async_set_value(hass, entity_id, value)

    assert exc.value.translation_key == translation_key
