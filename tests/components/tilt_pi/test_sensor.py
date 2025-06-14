"""Test the Tilt Hydrometer sensors."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tiltpi_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Tilt Pi sensors.

    When making changes to this test, ensure that the snapshot reflects the
    new data by generating it via:

        $ pytest tests/components/tilt_pi/test_sensor.py -v --snapshot-update
    """
    with patch("homeassistant.components.tilt_pi.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
