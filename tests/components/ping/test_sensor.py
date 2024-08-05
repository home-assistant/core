"""Test sensor platform of Ping."""

import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
@pytest.mark.parametrize(
    "sensor_name",
    [
        "round_trip_time_average",
        "round_trip_time_maximum",
        "round_trip_time_mean_deviation",  # should be None in the snapshot
        "round_trip_time_minimum",
    ],
)
async def test_setup_and_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    sensor_name: str,
) -> None:
    """Test sensor setup and update."""

    entry = entity_registry.async_get(f"sensor.10_10_10_10_{sensor_name}")
    assert entry == snapshot(exclude=props("unique_id"))

    state = hass.states.get(f"sensor.10_10_10_10_{sensor_name}")
    assert state == snapshot
