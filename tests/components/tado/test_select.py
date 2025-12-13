"""The select tests for the tado platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant

HEATING_CIRCUIT_SELECT_ENTITY = "select.baseboard_heater_heating_circuit"
NO_HEATING_CIRCUIT = "no_heating_circuit"
HEATING_CIRCUIT_OPTION = "RU1234567890"
ZONE_ID = 1
HEATING_CIRCUIT_ID = 1


@pytest.fixture(autouse=True)
def setup_platforms() -> Generator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_heating_circuit_select(hass: HomeAssistant) -> None:
    """Test creation of heating circuit select entity."""

    state = hass.states.get(HEATING_CIRCUIT_SELECT_ENTITY)
    assert state is not None
    assert state.state == HEATING_CIRCUIT_OPTION
    assert NO_HEATING_CIRCUIT in state.attributes["options"]
    assert HEATING_CIRCUIT_OPTION in state.attributes["options"]


@pytest.mark.parametrize(
    ("option", "expected_circuit_id"),
    [(HEATING_CIRCUIT_OPTION, HEATING_CIRCUIT_ID), (NO_HEATING_CIRCUIT, None)],
)
@pytest.mark.usefixtures("init_integration")
async def test_heating_circuit_select_action(
    hass: HomeAssistant, option, expected_circuit_id
) -> None:
    """Test selecting heating circuit option."""

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
