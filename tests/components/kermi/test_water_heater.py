"""Water heater tests for the Kermi component."""

from unittest.mock import Mock, patch

from homeassistant.components.kermi.water_heater import async_setup_entry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature


def test_init(kermi_water_heater) -> None:
    """Test the initialization."""
    assert kermi_water_heater._attr_name == "Test Heater"
    assert kermi_water_heater._attr_target_temperature == 0
    assert kermi_water_heater._attr_temperature_unit == UnitOfTemperature.CELSIUS
    assert kermi_water_heater._attr_current_operation == "auto"


def test_set_temperature(kermi_water_heater) -> None:
    """Test setting the temperature."""
    kermi_water_heater.hass = Mock()
    kermi_water_heater.set_temperature(**{ATTR_TEMPERATURE: 25})
    assert kermi_water_heater._attr_target_temperature == 25


def test_set_operation_mode(kermi_water_heater) -> None:
    """Test setting the operation mode."""
    kermi_water_heater.hass = Mock()
    kermi_water_heater.set_operation_mode("heat_pump")
    assert kermi_water_heater._attr_current_operation == "heat_pump"


@patch("homeassistant.components.kermi.water_heater.KermiWaterHeater")
async def test_async_setup_entry(
    mock_kermi_water_heater, mock_entry, mock_coordinator
) -> None:
    """Test a successful setup entry."""
    hass = Mock()
    hass.data = {"kermi": {mock_entry.entry_id: {"coordinator": mock_coordinator}}}
    async_add_entities = Mock()

    await async_setup_entry(hass, mock_entry, async_add_entities)

    mock_kermi_water_heater.assert_called_once_with(
        "Kermi x-buffer", mock_entry, mock_coordinator
    )
    async_add_entities.assert_called_once_with([mock_kermi_water_heater.return_value])
