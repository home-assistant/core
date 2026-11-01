"""Tests for PAJ GPS sensor platform."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pajgps_api.models.device import Device
from pajgps_api.models.sensordata import SensorData
from pajgps_api.models.trackpoint import TrackPoint
from pajgps_api.pajgps_api_error import PajGpsApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.paj_gps.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
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


@pytest.fixture
def mock_paj_gps_api_with_voltage(mock_paj_gps_api: AsyncMock) -> AsyncMock:
    """Override get_devices to return a device with voltage sensor support."""
    mock_paj_gps_api.get_devices.return_value = [
        Device(
            **{
                **load_json_object_fixture("device.json", DOMAIN),
                "device_models": [{"alarm_volt": 1}],
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


@pytest.mark.usefixtures("mock_paj_gps_api_with_voltage")
async def test_voltage_sensor_created_when_has_voltage_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a voltage sensor is created when alarm_volt is supported."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_paj_gps_api")
async def test_voltage_sensor_not_created_when_no_voltage_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no voltage sensor is created when alarm_volt is not supported."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.device_1_voltage") is None


async def test_voltage_none_when_missing(
    hass: HomeAssistant,
    mock_paj_gps_api_with_voltage: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that voltage state is unknown when SensorData has no volt value."""
    mock_paj_gps_api_with_voltage.get_last_sensor_data.return_value = SensorData(
        did=1,
        volt=None,
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.device_1_voltage")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_voltage_partial_degrade_when_one_sensor_data_call_fails(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test one failed sensor-data request does not break all voltage sensors."""
    mock_paj_gps_api.get_devices.return_value = [
        Device(
            id=1,
            name="Device 1",
            imei="IMEI1",
            modellid=100,
            device_models=[{"alarm_volt": 1}],
        ),
        Device(
            id=2,
            name="Device 2",
            imei="IMEI2",
            modellid=100,
            device_models=[{"alarm_volt": 1}],
        ),
    ]
    mock_paj_gps_api.get_all_last_positions.return_value = [
        TrackPoint(iddevice=1, speed=50),
        TrackPoint(iddevice=2, speed=40),
    ]

    device_sensor_data = {
        1: AsyncMock(return_value=SensorData(did=1, volt=12400)),
        2: AsyncMock(side_effect=PajGpsApiError("boom")),
    }

    async def _get_last_sensor_data(device_id: int) -> SensorData:
        return await device_sensor_data[device_id]()

    mock_paj_gps_api.get_last_sensor_data.side_effect = _get_last_sensor_data

    await setup_integration(hass, mock_config_entry)

    state_1 = hass.states.get("sensor.device_1_voltage")
    assert state_1 is not None
    assert state_1.state == "12.4"

    state_2 = hass.states.get("sensor.device_2_voltage")
    assert state_2 is not None
    assert state_2.state == STATE_UNAVAILABLE
    assert (
        caplog.messages.count("Failed to fetch voltage sensor data for device 2: boom")
        == 1
    )

    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert (
        caplog.messages.count("Failed to fetch voltage sensor data for device 2: boom")
        == 1
    )

    device_sensor_data[2].side_effect = None
    device_sensor_data[2].return_value = SensorData(did=2, volt=12500)
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert caplog.messages.count("Voltage sensor data recovered for device 2") == 1
    state_2 = hass.states.get("sensor.device_2_voltage")
    assert state_2 is not None
    assert state_2.state == "12.5"

    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert caplog.messages.count("Voltage sensor data recovered for device 2") == 1
