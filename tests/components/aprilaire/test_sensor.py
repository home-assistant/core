"""Tests for the Aprilaire sensor platform."""

from pyaprilaire.const import Attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_MAC, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.SENSOR]


pytestmark = [
    pytest.mark.usefixtures("mock_aprilaire"),
]


def _get_entity_id(
    entity_registry: er.EntityRegistry, unique_id_suffix: str
) -> str | None:
    """Get entity_id from the entity registry by unique_id suffix."""
    return entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, "aprilaire", f"{MOCK_MAC}_{unique_id_suffix}"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor entities via snapshot."""
    entry = await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_unavailable_when_disconnected(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    base_coordinator_data: dict,
) -> None:
    """Test sensors become unavailable when disconnected."""
    base_coordinator_data[Attribute.CONNECTED] = False
    base_coordinator_data[Attribute.RECONNECTING] = False
    await setup_integration(hass, mock_config_entry)

    entity_id = _get_entity_id(entity_registry, "indoor_humidity_controlling_sensor")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"


async def test_sensor_not_created_when_status_missing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    base_coordinator_data: dict,
) -> None:
    """Test sensors are not created when status indicates they don't exist."""
    # Status value 3+ means sensor doesn't exist for humidity/temperature sensors
    base_coordinator_data[Attribute.OUTDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS] = 3
    await setup_integration(hass, mock_config_entry)

    assert (
        _get_entity_id(entity_registry, "outdoor_temperature_controlling_sensor")
        is None
    )
