"""Test the Tado select platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

ENTITY_ID = "select.baseboard_heater_heating_circuit"


@pytest.mark.usefixtures("init_integration")
async def test_heating_circuit_select(hass: HomeAssistant) -> None:
    """Test the heating circuit select entity is created for heating zones."""
    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == "RU1234"
    assert state.attributes[ATTR_OPTIONS] == [
        "no_heating_circuit",
        "RU1234",
        "RU5678",
    ]


@pytest.mark.usefixtures("init_integration")
async def test_select_heating_circuit(hass: HomeAssistant) -> None:
    """Test selecting another heating circuit sends its number to Tado."""
    with patch("PyTado.interface.Tado.set_zone_heating_circuit") as mock_set:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "RU5678"},
            blocking=True,
        )

    mock_set.assert_called_once_with(1, 2)
    assert hass.states.get(ENTITY_ID).state == "RU5678"


@pytest.mark.usefixtures("init_integration")
async def test_clear_heating_circuit(hass: HomeAssistant) -> None:
    """Test the no-circuit option clears the assignment."""
    with patch("PyTado.interface.Tado.set_zone_heating_circuit") as mock_set:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "no_heating_circuit"},
            blocking=True,
        )

    mock_set.assert_called_once_with(1, None)
    assert hass.states.get(ENTITY_ID).state == "no_heating_circuit"


@pytest.mark.usefixtures("init_integration")
async def test_no_select_for_non_heating_zones(hass: HomeAssistant) -> None:
    """Test water heater and AC zones do not get a heating circuit select."""
    assert hass.states.get("select.water_heater_heating_circuit") is None
    assert hass.states.get("select.air_conditioning_heating_circuit") is None


@pytest.mark.usefixtures("init_integration")
async def test_heating_circuits_are_only_fetched_once(hass: HomeAssistant) -> None:
    """Test a coordinator refresh does not re-read the circuit configuration.

    This is the whole point of the design: the recurring call count must not
    grow with this feature (see #149670).
    """
    coordinator = hass.config_entries.async_entries("tado")[0].runtime_data

    with (
        patch("PyTado.interface.Tado.get_heating_circuits") as mock_circuits,
        patch("PyTado.interface.Tado.get_zone_control") as mock_control,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    mock_circuits.assert_not_called()
    mock_control.assert_not_called()
