"""Test BMW sensors."""
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from . import setup_mock_component


@pytest.mark.parametrize(
    "entity_id,metric,imperial",
    [
        ("sensor.x3_xdrive30e_remaining_range_total", ("516", "km"), ("320.63", "mi")),
        ("sensor.x3_xdrive30e_mileage", ("1121", "km"), ("696.56", "mi")),
        ("sensor.x3_xdrive30e_remaining_battery_percent", ("80", "%"), ("80", "%")),
        ("sensor.x3_xdrive30e_remaining_range_electric", ("40", "km"), ("24.85", "mi")),
        ("sensor.x3_xdrive30e_remaining_fuel", ("40", "L"), ("10.57", "gal")),
        ("sensor.x3_xdrive30e_remaining_range_fuel", ("476", "km"), ("295.77", "mi")),
        ("sensor.x3_xdrive30e_remaining_fuel_percent", ("80", "%"), ("80", "%")),
    ],
)
async def test_unit_conversion(
    hass: HomeAssistant,
    entity_id: str,
    metric: tuple[str, str],
    imperial: tuple[str, str],
) -> None:
    """Test conversion between metric and imperial units for sensors."""

    for unit_system in [METRIC_SYSTEM, IMPERIAL_SYSTEM]:
        # Set unit system
        hass.config.units = unit_system

        # Store corresponding expected value
        assertion_value = metric if unit_system.is_metric else imperial

        # Setup component
        mock_config_entry = await setup_mock_component(hass)

        # Test
        entity = hass.states.get(entity_id)
        assert entity.state == assertion_value[0]
        assert entity.attributes.get("unit_of_measurement") == assertion_value[1]

        # Unload config entry to start other unit system from scratch
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
