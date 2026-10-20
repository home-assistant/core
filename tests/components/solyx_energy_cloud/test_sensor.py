"""Tests for the Solyx Energy sensor platform."""

from typing import TYPE_CHECKING

import pytest

from homeassistant.components.solyx_energy_cloud.const import DOMAIN

from .const import NYMO_DEVICE_ID, NYMO_DEVICE_ID_2

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_registry import EntityRegistry


@pytest.mark.parametrize(
    ("device_id", "key", "expected"),
    [
        pytest.param(
            NYMO_DEVICE_ID,
            "boiler_current",
            ("5.2", "A", "current", "measurement"),
            id="boiler_current",
        ),
        pytest.param(
            NYMO_DEVICE_ID,
            "boiler_power",
            ("1234.0", "W", "power", "measurement"),
            id="boiler_power",
        ),
        pytest.param(
            NYMO_DEVICE_ID,
            "boiler_voltage",
            ("230.0", "V", "voltage", "measurement"),
            id="boiler_voltage",
        ),
        pytest.param(
            NYMO_DEVICE_ID,
            "days_since_maximum_temperature",
            ("3.0", "d", "duration", "measurement"),
            id="days_since_maximum_temperature",
        ),
        pytest.param(
            NYMO_DEVICE_ID,
            "grid_power",
            ("-100.0", "W", "power", "measurement"),
            id="grid_power",
        ),
        pytest.param(
            NYMO_DEVICE_ID,
            "legionella_days",
            ("7.0", "d", "duration", "measurement"),
            id="legionella_days",
        ),
        pytest.param(
            NYMO_DEVICE_ID,
            "saved_this_month",
            ("12.5", "kWh", "energy", "total_increasing"),
            id="saved_this_month",
        ),
        pytest.param(
            NYMO_DEVICE_ID,
            "saved_this_week",
            ("3.2", "kWh", "energy", "total_increasing"),
            id="saved_this_week",
        ),
        pytest.param(
            NYMO_DEVICE_ID,
            "saved_today",
            ("0.4", "Wh", "energy", "total_increasing"),
            id="saved_today",
        ),
        pytest.param(
            NYMO_DEVICE_ID_2,
            "boiler_power",
            ("567.0", "W", "power", "measurement"),
            id="boiler_power_2",
        ),
        pytest.param(
            NYMO_DEVICE_ID_2,
            "grid_power",
            ("42.0", "W", "power", "measurement"),
            id="grid_power_2",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensor_states(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_id: str,
    key: str,
    expected: tuple[str, str, str, str],
) -> None:
    """Test each sensor has the correct state, unit, device class, and state class."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{device_id}-{key}"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    value, unit, device_class, state_class = expected
    assert state.state == value
    assert state.attributes["unit_of_measurement"] == unit
    assert state.attributes["device_class"] == device_class
    assert state.attributes["state_class"] == state_class
