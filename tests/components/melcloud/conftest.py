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


def _build_mock_zone(zone_index: int) -> MagicMock:
    """Build a mock Zone object."""
    zone = MagicMock()
    zone.zone_index = zone_index
    zone.name = f"Zone {zone_index}"
    zone.room_temperature = 21.5 + zone_index
    zone.zone_flow_temperature = 35.0 + zone_index
    zone.zone_return_temperature = 30.0 + zone_index
    return zone


def _build_mock_atw_device() -> MagicMock:
    """Build a mock AtwDevice with all properties."""
    device = MagicMock()
    device.device_id = "atw001"
    device.building_id = "building001"
    device.mac = MOCK_MAC
    device.serial = MOCK_SERIAL
    device.name = "Ecodan"
    device.units = [{"model": "ATW-Unit", "serial": "unit-serial-1"}]

    # Binary sensor properties
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

    # Existing ATW sensors
    device.outside_temperature = 7.5
    device.tank_temperature = 48.0

    # New temperature sensors
    device.flow_temperature = 38.5
    device.return_temperature = 33.2
    device.flow_temperature_boiler = 40.1
    device.return_temperature_boiler = 35.3
    device.mixing_tank_temperature = 42.0
    device.condensing_temperature = 55.0
    device.heat_pump_frequency = 52
    device.demand_percentage = 75
    device.wifi_signal = -65
    device.get_device_prop = MagicMock(return_value=3.5)

    # Daily energy
    device.daily_heating_energy_consumed = 12.5
    device.daily_heating_energy_produced = 35.0
    device.daily_cooling_energy_consumed = 0.0
    device.daily_cooling_energy_produced = 0.0
    device.daily_hot_water_energy_consumed = 5.2
    device.daily_hot_water_energy_produced = 14.8

    # Zones
    device.zones = [_build_mock_zone(1)]

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
