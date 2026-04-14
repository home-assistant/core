"""Test helpers for MELCloud."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pymelcloud
import pytest

from homeassistant.components.melcloud.const import DOMAIN
from homeassistant.const import CONF_TOKEN

from tests.common import MockConfigEntry

MOCK_SERIAL = "ABC123456"
MOCK_MAC = "AA:BB:CC:DD:EE:FF"


def _build_mock_atw_device() -> MagicMock:
    """Build a mock AtwDevice with all properties."""
    device = MagicMock()
    device.device_id = "atw001"
    device.building_id = "building001"
    device.mac = MOCK_MAC
    device.serial = MOCK_SERIAL
    device.name = "Ecodan"
    device.units = [{"model": "ATW-Unit", "serial": "unit-serial-1"}]

    device.boiler_status = True
    device.booster_heater1_status = False
    device.booster_heater2_status = None
    device.booster_heater2plus_status = None
    device.immersion_heater_status = False
    device.water_pump1_status = True
    device.water_pump2_status = False
    device.water_pump3_status = None
    device.water_pump4_status = None
    device.valve_3way_status = True
    device.valve_2way_status = None

    device.zones = []

    device.update = AsyncMock()

    return device


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a MELCloud config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test-email@example.com",
        data={
            CONF_TOKEN: "test-token",
            "username": "test-email@example.com",
        },
        entry_id="melcloud_test_entry",
        unique_id="test-email@example.com",
    )


@pytest.fixture
def mock_atw_device() -> MagicMock:
    """Return the mock ATW device for direct access in tests."""
    return _build_mock_atw_device()


@pytest.fixture
def mock_get_devices(mock_atw_device: MagicMock) -> Generator[MagicMock]:
    """Mock pymelcloud.get_devices with a single ATW device."""

    async def _get_devices(**kwargs):
        return {
            pymelcloud.DEVICE_TYPE_ATA: [],
            pymelcloud.DEVICE_TYPE_ATW: [mock_atw_device],
        }

    with patch(
        "homeassistant.components.melcloud.get_devices",
        side_effect=_get_devices,
    ) as mock:
        yield mock
