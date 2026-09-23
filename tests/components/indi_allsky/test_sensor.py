"""Tests for the INDI Allsky sensor platform."""

from unittest.mock import AsyncMock, patch

from aioindiallsky import SensorData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_indi_allsky_client"
)
async def test_sensor_setup_and_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test standard successful setup and entity snapshots using snapshot_platform."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.usefixtures("mock_indi_allsky_client")
async def test_disabled_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that disabled-by-default sensors are registered as disabled."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    for entity_id in (
        "sensor.indi_allsky_binning_mode",
        "sensor.indi_allsky_cpu_temperature",
        "sensor.indi_allsky_filename",
        "sensor.indi_allsky_gain",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    for entity_id in (
        "sensor.indi_allsky_camera_sensor_temperature",
        "sensor.indi_allsky_dew_heater_duty_cycle",
        "sensor.indi_allsky_exposure_time",
        "sensor.indi_allsky_sky_quality",
        "sensor.indi_allsky_stars",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is None


async def test_hardware_sensor_updates(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: SensorData,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test hardware sensor state values update on sensor_update event."""
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_cpu_temperature",
        suggested_object_id="indi_allsky_cpu_temperature",
        disabled_by=None,
    )

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(mock_sensor_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_ambient_temperature")
    assert state is not None
    assert state.state == "21.5"

    state = hass.states.get("sensor.indi_allsky_humidity")
    assert state is not None
    assert state.state == "65.0"

    state = hass.states.get("sensor.indi_allsky_pressure")
    assert state is not None
    assert state.state == "1013.25"

    state = hass.states.get("sensor.indi_allsky_dew_point")
    assert state is not None
    assert state.state == "14.8"

    state = hass.states.get("sensor.indi_allsky_cpu_temperature")
    assert state is not None
    assert state.state == "45.2"


async def test_hardware_sensor_fallback_updates(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test hardware sensor fallback resolution from raw_user and raw_temp slots."""
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_cpu_temperature",
        suggested_object_id="indi_allsky_cpu_temperature",
        disabled_by=None,
    )

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    fallback_data = SensorData.from_dict(
        {
            "sensors": {},
            "sensor_temp": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 57.5],
            "sensor_user": [0, 0, 0, 0, 0, 0, 0, 0, 0, 12500.5],
        }
    )

    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(fallback_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_cpu_temperature")
    assert state is not None
    assert state.state == "57.5"

    state = hass.states.get("sensor.indi_allsky_camera_sqm_adu")
    assert state is not None
    assert state.state == "12500.5"


async def test_dynamic_hardware_sensor_discovery(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test dynamic discovery and metadata inference of custom hardware sensors."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    dynamic_data = SensorData.from_dict(
        {
            "sensors": {
                "sensor_a_temperature": {
                    "name": "SHT4x (i2c) - SHT40 - Temperature",
                    "value": 30.83,
                    "unit": "°C",
                    "device_class": "temperature",
                },
                "sensor_b_pressure": {
                    "name": "Ecowitt API - Sensor B - Pressure",
                    "value": 1017.27,
                    "unit": "hPa",
                    "device_class": "pressure",
                },
                "sensor_c_humidity": {
                    "name": "DHT22 - Sensor C - Humidity",
                    "value": 65.5,
                    "unit": "%",
                },
            }
        }
    )

    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(dynamic_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_sht4x_i2c_sht40_temperature")
    assert state is not None
    assert state.state == "30.83"
    assert state.attributes.get("unit_of_measurement") == "°C"
    assert state.attributes.get("device_class") == "temperature"

    state = hass.states.get("sensor.indi_allsky_ecowitt_api_sensor_b_pressure")
    assert state is not None
    assert state.state == "1017.27"
    assert state.attributes.get("unit_of_measurement") == "hPa"
    assert state.attributes.get("device_class") == "pressure"

    state = hass.states.get("sensor.indi_allsky_dht22_sensor_c_humidity")
    assert state is not None
    assert state.state == "65.5"
    assert state.attributes.get("unit_of_measurement") == "%"
