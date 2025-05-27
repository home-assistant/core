"""Test sensor platform for Swing2Sleep Smarla integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pysmarlaapi.federwiege.classes import Property
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


def mock_get_property(service, property) -> MagicMock:
    """Mock the get_property method of the Federwiege class for sensor properties."""
    prop = MagicMock(spec=Property)
    if property == "oscillation":
        prop.get.return_value = [1, 1]
    else:
        prop.get.return_value = 1
    return prop


@pytest.fixture
def sensor_platform_patch() -> Generator:
    """Limit integration to sensor platform."""
    with (
        patch("homeassistant.components.smarla.PLATFORMS", [Platform.SENSOR]),
    ):
        yield


async def test_entities(
    hass: HomeAssistant,
    sensor_platform_patch,
    mock_federwiege: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Smarla entities."""
    mock_federwiege.get_property = MagicMock(side_effect=mock_get_property)

    assert await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
