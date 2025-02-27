"""Test the Tilt Hydrometer sensors."""

from unittest.mock import Mock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.tilt_pi.coordinator import TiltPiDataUpdateCoordinator
from homeassistant.components.tilt_pi.model import TiltHydrometerData
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_HOST, TEST_PORT

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_tilt_data() -> TiltHydrometerData:
    """Create mock tilt data."""
    return TiltHydrometerData(
        mac_id="00:1A:2B:3C:4D:5E",
        color="Purple",
        temperature=68.0,
        gravity=1.052,
    )


@pytest.fixture
def mock_coordinator(mock_tilt_data) -> TiltPiDataUpdateCoordinator:
    """Create a mock coordinator."""
    coordinator = Mock()
    coordinator.data = [mock_tilt_data]
    return coordinator


async def test_all_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Tilt Pi sensors.

    When making changes to this test, ensure that the snapshot reflects the
    new data by generating it via:

        $ pytest tests/components/tilt_pi/test_sensor.py -v --snapshot-update
    """
    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/macid/all",
        json=[
            {
                "mac": "00:1A:2B:3C:4D:5E",
                "Color": "BLACK",
                "SG": 1.010,
                "Temp": "55.0",
            },
            {
                "mac": "00:1s:99:f1:d2:4f",
                "Color": "YELLOW",
                "SG": 1.015,
                "Temp": "68.0",
            },
        ],
    )

    with patch("homeassistant.components.tilt_pi.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
