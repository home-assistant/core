"""Test BMW sensors."""
from freezegun import freeze_time
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import (
    METRIC_SYSTEM as METRIC,
    US_CUSTOMARY_SYSTEM as IMPERIAL,
    UnitSystem,
)

from . import setup_mocked_integration


@freeze_time("2023-06-22 10:30:00+00:00")
async def test_entity_state_attrs(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor options and values.."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Get all select entities
    assert hass.states.async_all("sensor") == snapshot


@pytest.mark.parametrize(
    ("entity_id", "unit_system", "value", "unit_of_measurement"),
    [
        ("sensor.i3_rex_remaining_range_total", METRIC, "279", "km"),
        ("sensor.i3_rex_remaining_range_total", IMPERIAL, "173.36", "mi"),
        ("sensor.i3_rex_mileage", METRIC, "137009", "km"),
        ("sensor.i3_rex_mileage", IMPERIAL, "85133.45", "mi"),
        ("sensor.i3_rex_remaining_battery_percent", METRIC, "82", "%"),
        ("sensor.i3_rex_remaining_battery_percent", IMPERIAL, "82", "%"),
        ("sensor.i3_rex_remaining_range_electric", METRIC, "174", "km"),
        ("sensor.i3_rex_remaining_range_electric", IMPERIAL, "108.12", "mi"),
        ("sensor.i3_rex_remaining_fuel", METRIC, "6", "L"),
        ("sensor.i3_rex_remaining_fuel", IMPERIAL, "1.59", "gal"),
        ("sensor.i3_rex_remaining_range_fuel", METRIC, "105", "km"),
        ("sensor.i3_rex_remaining_range_fuel", IMPERIAL, "65.24", "mi"),
        ("sensor.m340i_xdrive_remaining_fuel_percent", METRIC, "80", "%"),
        ("sensor.m340i_xdrive_remaining_fuel_percent", IMPERIAL, "80", "%"),
    ],
)
async def test_unit_conversion(
    hass: HomeAssistant,
    entity_id: str,
    unit_system: UnitSystem,
    value: str,
    unit_of_measurement: str,
    bmw_fixture,
) -> None:
    """Test conversion between metric and imperial units for sensors."""

    # Set unit system
    hass.config.units = unit_system

    # Setup component
    assert await setup_mocked_integration(hass)

    # Test
    entity = hass.states.get(entity_id)
    assert entity.state == value
    assert entity.attributes.get("unit_of_measurement") == unit_of_measurement
