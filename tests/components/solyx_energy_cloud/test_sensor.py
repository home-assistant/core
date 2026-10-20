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
            "boiler_power",
            ("1234.0", "W", "power"),
            id="boiler_power",
        ),
        pytest.param(
            NYMO_DEVICE_ID,
            "grid_power",
            ("-100.0", "W", "power"),
            id="grid_power",
        ),
        pytest.param(
            NYMO_DEVICE_ID_2,
            "boiler_power",
            ("567.0", "W", "power"),
            id="boiler_power_2",
        ),
        pytest.param(
            NYMO_DEVICE_ID_2,
            "grid_power",
            ("42.0", "W", "power"),
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
    expected: tuple[str, str, str],
) -> None:
    """Test each sensor has the correct state, unit, and device class."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{device_id}-{key}"
    )
    assert entity_id is not None

    # Check the state, unit, and device class match the API data.
    state = hass.states.get(entity_id)
    assert state is not None
    value, unit, device_class = expected
    assert state.state == value
    assert state.attributes["unit_of_measurement"] == unit
    assert state.attributes["device_class"] == device_class
