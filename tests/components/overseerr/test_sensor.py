"""Test the Overseerr sensor platform."""
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("setup_integration")
async def test_overseerr_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the overseerr sensor states."""
    sensor_names = [
        "movie_requests",
        "tv_requests",
        "approved_requests",
        "available_requests",
        "pending_requests",
        "total_requests",
    ]

    for sensor_name in sensor_names:
        entry = entity_registry.async_get(f"sensor.mock_title_{sensor_name}")
        assert entry == snapshot(name=f"entry-{sensor_name}")

        state = hass.states.get(f"sensor.mock_title_{sensor_name}")
        assert state == snapshot(name=f"state-{sensor_name}")
