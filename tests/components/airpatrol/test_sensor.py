"""Test the AirPatrol sensor platform."""

from airpatrol.api import AirPatrolAPI
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform


@pytest.mark.parametrize(
    "climate_data",
    [
        {
            "ParametersData": {
                "PumpPower": "on",
                "PumpTemp": "22.000",
                "PumpMode": "cool",
                "FanSpeed": "max",
                "Swing": "off",
            },
            "RoomTemp": "22.5",
            "RoomHumidity": "45",
        },
        None,
    ],
)
@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SENSOR]],
)
async def test_sensor(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entities."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        load_integration.entry_id,
    )
