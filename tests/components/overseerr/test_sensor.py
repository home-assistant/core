"""Test the Overseerr sensor platform."""
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    "sensor_name",
    [
        "movie_requests",
        "tv_requests",
        "approved_requests",
        "available_requests",
        "pending_requests",
        "total_requests",
    ],
)
async def test_overseerr_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    sensor_name: str,
) -> None:
    """Test the overseerr sensor states."""
    entry = entity_registry.async_get(f"sensor.mock_title_{sensor_name}")
    assert entry == snapshot(exclude=props("unique_id"))

    state = hass.states.get(f"sensor.mock_title_{sensor_name}")
    assert state == snapshot
