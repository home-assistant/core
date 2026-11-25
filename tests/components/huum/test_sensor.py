"""Tests for the Huum sensor entity."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

TEMPERATURE_ENTITY_ID = "sensor.huum_sauna_temperature"
MEASURED_HUMIDITY_ENTITY_ID = "sensor.huum_sauna_measured_humidity"


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_measured_humidity_sensor(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the humidity sensor is not created without a measured value."""
    mock_huum_client.status.return_value.measured_humidity = None

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.huum.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_ENTITY_ID) is not None
    assert hass.states.get(MEASURED_HUMIDITY_ENTITY_ID) is None
