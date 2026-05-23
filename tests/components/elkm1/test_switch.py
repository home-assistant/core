"""Test the Elk-M1 switch platform."""

from unittest.mock import MagicMock

from elkm1_lib.const import ThermostatMode, ThermostatSetting
import pytest

from homeassistant.components.elkm1.switch import ElkThermostatEMHeat


@pytest.fixture
def emheat_entity() -> ElkThermostatEMHeat:
    """Return an ElkThermostatEMHeat entity with mocked dependencies."""
    element = MagicMock()
    element.name = "Downstairs"
    element.default_name.return_value = "downstairs"
    element.index = 0

    elk = MagicMock()

    elk_data = MagicMock()
    elk_data.mac = "aa:bb:cc:dd:ee:ff"
    elk_data.prefix = ""
    elk_data.auto_configure = True
    elk_data.config = {"temperature_unit": "F"}

    return ElkThermostatEMHeat(element, elk, elk_data)


@pytest.mark.parametrize(
    ("method", "expected_mode"),
    [
        pytest.param("async_turn_on", ThermostatMode.EMERGENCY_HEAT, id="turn_on"),
        pytest.param("async_turn_off", ThermostatMode.HEAT, id="turn_off"),
    ],
)
async def test_emheat_actions(
    emheat_entity: ElkThermostatEMHeat,
    method: str,
    expected_mode: ThermostatMode,
) -> None:
    """Test emergency heat turn on/off sets the correct thermostat mode."""
    await getattr(emheat_entity, method)()
    emheat_entity._element.set.assert_called_once_with(
        ThermostatSetting.MODE, expected_mode
    )
