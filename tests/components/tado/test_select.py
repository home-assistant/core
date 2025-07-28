"""The select tests for the tado platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION
from homeassistant.core import HomeAssistant

from .util import async_init_integration

HEATING_CIRCUIT_SELECT_ENTITY = "select.baseboard_heater_heating_circuit"
NO_HEATING_CIRCUIT = "no_heating_circuit"
HEATING_CIRCUIT_OPTION = "RU1234567890"
ZONE_ID = 1
HEATING_CIRCUIT_ID = 1


async def test_heating_circuit_select(hass: HomeAssistant) -> None:
    """Test creation of heating circuit select entity."""

    await async_init_integration(hass)
    state = hass.states.get(HEATING_CIRCUIT_SELECT_ENTITY)
    assert state is not None
    assert state.state == HEATING_CIRCUIT_OPTION
    assert NO_HEATING_CIRCUIT in state.attributes["options"]
    assert HEATING_CIRCUIT_OPTION in state.attributes["options"]


@pytest.mark.parametrize(
    ("option", "expected_circuit_id"),
    [(HEATING_CIRCUIT_OPTION, HEATING_CIRCUIT_ID), (NO_HEATING_CIRCUIT, None)],
)
async def test_heating_circuit_select_action(
    hass: HomeAssistant, option, expected_circuit_id
) -> None:
    """Test selecting heating circuit option."""

    await async_init_integration(hass)

    # Test selecting a specific heating circuit
    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_zone_heating_circuit"
        ) as mock_set_zone_heating_circuit,
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.get_zone_control"
        ) as mock_get_zone_control,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: HEATING_CIRCUIT_SELECT_ENTITY,
                ATTR_OPTION: option,
            },
            blocking=True,
        )

    mock_set_zone_heating_circuit.assert_called_with(ZONE_ID, expected_circuit_id)
    assert mock_get_zone_control.called


@pytest.mark.usefixtures("caplog")
async def test_heating_circuit_not_found(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when a heating circuit with a specific number is not found."""
    circuit_not_matching_zone_control = 999
    heating_circuits = [
        {
            "number": circuit_not_matching_zone_control,
            "driverSerialNo": "RU1234567890",
            "driverShortSerialNo": "RU1234567890",
        }
    ]

    with patch(
        "homeassistant.components.tado.PyTado.interface.api.Tado.get_heating_circuits",
        return_value=heating_circuits,
    ):
        await async_init_integration(hass)

    state = hass.states.get(HEATING_CIRCUIT_SELECT_ENTITY)
    assert state.state == NO_HEATING_CIRCUIT

    assert "Heating circuit with number 1 not found for zone" in caplog.text
