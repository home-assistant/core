"""Tests for PAJ GPS sensor platform."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pajgps_api.models.device import Device
from pajgps_api.models.trackpoint import TrackPoint
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.paj_gps.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.paj_gps.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


async def test_speed_none_when_missing(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that speed state is unknown when the trackpoint has no speed value."""
    mock_paj_gps_api.get_all_last_positions.return_value = [
        TrackPoint(iddevice=1, speed=None)
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.device_1_speed")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.fixture
def mock_paj_gps_api_with_battery(mock_paj_gps_api: AsyncMock) -> AsyncMock:
    """Override get_devices to return a device with a standalone battery."""
    mock_paj_gps_api.get_devices.return_value = [
        Device(
            **{
                **load_json_object_fixture("device.json", DOMAIN),
                "device_models": [{"standalone_battery": 1}],
            }
        )
    ]
    return mock_paj_gps_api


@pytest.mark.usefixtures("mock_paj_gps_api_with_battery")
async def test_battery_sensor_created_when_has_battery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a battery sensor is created for devices with a standalone battery."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_paj_gps_api")
async def test_battery_sensor_not_created_when_no_battery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no battery sensor is created for devices without a standalone battery."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.device_1_battery") is None


async def test_battery_none_when_missing(
    hass: HomeAssistant,
    mock_paj_gps_api_with_battery: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that battery state is unknown when the trackpoint has no battery_level value."""
    mock_paj_gps_api_with_battery.get_all_last_positions.return_value = [
        TrackPoint(iddevice=1, battery_level=None)
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.device_1_battery")
    assert state is not None
    assert state.state == STATE_UNKNOWN
