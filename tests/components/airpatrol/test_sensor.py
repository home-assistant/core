"""Test the AirPatrol sensor platform."""

from collections.abc import Generator
from unittest.mock import patch

from airpatrol.api import AirPatrolAPI
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override the platforms to load for airpatrol."""
    with patch(
        "homeassistant.components.airpatrol.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


async def test_sensor_with_climate_data(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entities are created with climate data."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        load_integration.entry_id,
    )


@pytest.mark.parametrize(
    "climate_data",
    [
        None,
    ],
)
async def test_sensor_with_no_climate_data(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    get_client: AirPatrolAPI,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no sensor entities are created when no climate data is present."""
    assert len(entity_registry.entities) == 0
