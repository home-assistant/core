"""Tests for the INDI Allsky sensor platform."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioindiallsky import ExposureData, SensorData
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.indi_allsky.coordinator import IndiAllSkyData
from homeassistant.components.indi_allsky.sensor import _parse_timestamp
from homeassistant.const import STATE_UNKNOWN, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import setup_integration


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
        "sensor.indi_allsky_camera_id",
        "sensor.indi_allsky_cpu_temperature",
        "sensor.indi_allsky_exposure_creation_time",
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


async def test_exposure_sensor_updates(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_exposure_data: ExposureData,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor state values update on exposure_complete event."""
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_binmode",
        suggested_object_id="indi_allsky_binning_mode",
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_camera_id",
        suggested_object_id="indi_allsky_camera_id",
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_create_date",
        suggested_object_id="indi_allsky_exposure_creation_time",
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_filename",
        suggested_object_id="indi_allsky_filename",
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_gain",
        suggested_object_id="indi_allsky_gain",
        disabled_by=None,
    )

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    for callback in mock_indi_allsky_client.callbacks.get("exposure_complete", []):
        callback(mock_exposure_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_exposure_time")
    assert state is not None
    assert state.state == "0.185"

    state = hass.states.get("sensor.indi_allsky_camera_sensor_temperature")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("sensor.indi_allsky_sky_quality")
    assert state is not None
    assert state.state == "32928.83"

    state = hass.states.get("sensor.indi_allsky_stars")
    assert state is not None
    assert state.state == "0"

    state = hass.states.get("sensor.indi_allsky_binning_mode")
    assert state is not None
    assert state.state == "1"

    state = hass.states.get("sensor.indi_allsky_filename")
    assert state is not None
    assert state.state == "test.jpg"

    state = hass.states.get("sensor.indi_allsky_gain")
    assert state is not None
    assert state.state == "0.0"

    state = hass.states.get("sensor.indi_allsky_camera_id")
    assert state is not None
    assert state.state == "1"

    state = hass.states.get("sensor.indi_allsky_exposure_creation_time")
    assert state is not None
    assert state.state == "2026-08-13T22:53:41+00:00"

    for callback in mock_indi_allsky_client.callbacks.get("exposure_complete", []):
        callback(replace(mock_exposure_data, temp=12.5, adu=512.0, hfr=2.4))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_camera_sensor_temperature")
    assert state is not None
    assert state.state == "12.5"


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

    state = hass.states.get("sensor.indi_allsky_dew_heater_duty_cycle")
    assert state is not None
    assert state.state == "50.0"

    state = hass.states.get("sensor.indi_allsky_dew_point")
    assert state is not None
    assert state.state == "14.8"

    state = hass.states.get("sensor.indi_allsky_frost_point")
    assert state is not None
    assert state.state == "10.2"

    state = hass.states.get("sensor.indi_allsky_fan_duty_cycle")
    assert state is not None
    assert state.state == "75.0"

    state = hass.states.get("sensor.indi_allsky_heat_index")
    assert state is not None
    assert state.state == "22.1"

    state = hass.states.get("sensor.indi_allsky_wind_direction")
    assert state is not None
    assert state.state == "180.0"

    state = hass.states.get("sensor.indi_allsky_device_sqm")
    assert state is not None
    assert state.state == "21.4"

    state = hass.states.get("sensor.indi_allsky_camera_sqm")
    assert state is not None
    assert state.state == "20.8"

    state = hass.states.get("sensor.indi_allsky_camera_sqm_adu")
    assert state is not None
    assert state.state == "15000.0"

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


async def test_consecutive_sensor_updates_merging(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test consecutive sensor updates merge retaining previous values."""
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_cpu_temperature",
        suggested_object_id="indi_allsky_cpu_temperature",
        disabled_by=None,
    )

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    first_update = SensorData.from_dict(
        {
            "sensors": {
                "humidity": 65.0,
            },
            "sensor_user": [0, 0, 14.8],
            "sensor_temp": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 42.0],
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(first_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_humidity")
    assert state is not None
    assert state.state == "65.0"

    state = hass.states.get("sensor.indi_allsky_dew_point")
    assert state is not None
    assert state.state == "14.8"

    state = hass.states.get("sensor.indi_allsky_cpu_temperature")
    assert state is not None
    assert state.state == "42.0"

    second_update = SensorData.from_dict(
        {
            "sensors": {
                "humidity": 70.0,
                "pressure": 1015.0,
            },
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(second_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_humidity")
    assert state is not None
    assert state.state == "70.0"

    state = hass.states.get("sensor.indi_allsky_pressure")
    assert state is not None
    assert state.state == "1015.0"

    state = hass.states.get("sensor.indi_allsky_dew_point")
    assert state is not None
    assert state.state == "14.8"

    state = hass.states.get("sensor.indi_allsky_cpu_temperature")
    assert state is not None
    assert state.state == "42.0"


async def test_hardware_sensor_fahrenheit_units(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test declared Fahrenheit temperature unit prevents double conversion."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="indi_allsky",
        unique_id=f"{mock_config_entry.entry_id}_cpu_temperature",
        suggested_object_id="indi_allsky_cpu_temperature",
        disabled_by=None,
    )

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    fahrenheit_update = SensorData.from_dict(
        {
            "temp_unit": "°F",
            "sensors": {
                "ambient_temperature": {
                    "name": "Ambient Temperature",
                    "value": 68.0,
                    "unit": "°F",
                },
                "dew_point": {
                    "name": "Dew Point",
                    "value": 55.4,
                    "unit": "°F",
                },
                "frost_point": {
                    "name": "Frost Point",
                    "value": 50.0,
                    "unit": "°F",
                },
                "heat_index": {
                    "name": "Heat Index",
                    "value": 70.0,
                    "unit": "°F",
                },
                "sensor_temp_10": {
                    "name": "CPU Temperature",
                    "value": 113.0,
                    "unit": "°F",
                },
                "pressure": {
                    "name": "Pressure",
                    "value": 14.7,
                    "unit": "psi",
                },
            },
            "sensor_user": [0, 0, 55.4, 50.0, 0, 70.0],
            "sensor_temp": [32.0] * 10 + [113.0],
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(fahrenheit_update)
    await hass.async_block_till_done()

    for entity_id, expected in (
        ("sensor.indi_allsky_ambient_temperature", "68.0"),
        ("sensor.indi_allsky_dew_point", "55.4"),
        ("sensor.indi_allsky_frost_point", "50.0"),
        ("sensor.indi_allsky_heat_index", "70.0"),
        ("sensor.indi_allsky_cpu_temperature", "113.0"),
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected
        assert (
            state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT
        )

    pressure_state = hass.states.get("sensor.indi_allsky_pressure")
    assert pressure_state is not None
    assert pressure_state.state == "14.7"
    assert pressure_state.attributes.get("unit_of_measurement") == "psi"

    # Verify partial update without temp_unit preserves the declared °F unit
    partial_update = SensorData.from_dict(
        {
            "sensors": {
                "humidity": 60.0,
            }
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(partial_update)
    await hass.async_block_till_done()

    dew_state = hass.states.get("sensor.indi_allsky_dew_point")
    assert dew_state is not None
    assert dew_state.state == "55.4"
    assert (
        dew_state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT
    )

    # Verify update with per-sensor °C metadata (without top-level temp_unit) switches to °C
    celsius_metadata_update = SensorData.from_dict(
        {
            "sensors": {
                "dew_point": {
                    "name": "Dew Point",
                    "value": 20.0,
                    "unit": "°C",
                },
            },
            "sensor_user": [0, 0, 20.0],
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(celsius_metadata_update)
    await hass.async_block_till_done()

    for entity_id, expected in (
        ("sensor.indi_allsky_dew_point", "68.0"),
        ("sensor.indi_allsky_frost_point", "50.0"),
        ("sensor.indi_allsky_heat_index", "70.0"),
        ("sensor.indi_allsky_cpu_temperature", "113.0"),
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == pytest.approx(float(expected), abs=0.05)
        assert (
            state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT
        )

    # Return to Fahrenheit before verifying CPU-only Celsius transition
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(fahrenheit_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_cpu_temperature")
    assert state is not None
    assert state.state == "113.0"

    # Verify CPU-only update with sensor_temp_10 in °C switches unit to °C
    celsius_cpu_update = SensorData.from_dict(
        {
            "sensors": {
                "sensor_temp_10": {
                    "name": "CPU Temperature",
                    "value": 45.0,
                    "unit": "°C",
                },
            },
            "sensor_temp": [0.0] * 10 + [45.0],
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(celsius_cpu_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_cpu_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(113.0, abs=0.05)
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT

    # Return to Fahrenheit before verifying dynamic temperature unit reconciliation
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(fahrenheit_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_ambient_temperature")
    assert state is not None
    assert state.state == "68.0"

    # Verify update with global temp_unit °C reconciles dynamic ambient_temperature
    # supplied as scalar without per-sensor unit, publishing 20 °C converted to 68 °F
    celsius_ambient_scalar_update = SensorData.from_dict(
        {
            "temp_unit": "°C",
            "sensors": {
                "ambient_temperature": 20.0,
            },
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(celsius_ambient_scalar_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_ambient_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(68.0, abs=0.05)
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT

    # Also verify unitless dict update {"value": 25.0} reconciles to °C -> 77 °F
    celsius_ambient_dict_update = SensorData.from_dict(
        {
            "temp_unit": "°C",
            "sensors": {
                "ambient_temperature": {"value": 25.0},
            },
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(celsius_ambient_dict_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_ambient_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(77.0, abs=0.05)
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT

    # Return to Fahrenheit before verifying metadata-only updates do not relabel values
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(fahrenheit_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_ambient_temperature")
    assert state is not None
    assert state.state == "68.0"

    # Verify metadata-only update with temp_unit °C does not relabel cached reading
    metadata_only_update = SensorData.from_dict(
        {
            "temp_unit": "°C",
            "sensors": {
                "ambient_temperature": {"name": "Ambient Temp Renamed"},
            },
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(metadata_only_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_ambient_temperature")
    assert state is not None
    assert state.state == "68.0"
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT

    # Return to Fahrenheit before verifying staggered updates
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(fahrenheit_update)
    await hass.async_block_till_done()

    # Step 1: Global temp_unit switches to °C in an update that omits ambient_temperature
    staggered_step1 = SensorData.from_dict(
        {
            "temp_unit": "°C",
            "sensors": {
                "dew_point": 20.0,
            },
            "sensor_user": [0, 0, 20.0],
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(staggered_step1)
    await hass.async_block_till_done()

    # Step 2: Subsequent update declares temp_unit °C (no change in global unit)
    # and supplies fresh ambient_temperature without unit; must reconcile to °C
    staggered_step2 = SensorData.from_dict(
        {
            "temp_unit": "°C",
            "sensors": {
                "ambient_temperature": 20.0,
            },
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(staggered_step2)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_ambient_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(68.0, abs=0.05)
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.FAHRENHEIT


async def test_dynamic_hardware_sensor_discovery(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
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
                "sensor_d_lux": {
                    "name": "TSL2561 Lux",
                    "value": 150.0,
                    "unit": "lx",
                },
                "sensor_e_status": {
                    "name": "Hardware Status",
                    "value": "Operational",
                },
                "sensor_f_no_unit_temp": {
                    "name": "Generic Temperature Sensor",
                    "value": 24.5,
                },
                "lamp_status": {
                    "name": "Dome Lamp Status",
                    "value": "Off",
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

    state = hass.states.get("sensor.indi_allsky_tsl2561_lux")
    assert state is not None
    assert state.state == "150.0"
    assert state.attributes.get("unit_of_measurement") == "lx"
    assert state.attributes.get("device_class") == "illuminance"

    state = hass.states.get("sensor.indi_allsky_hardware_status")
    assert state is not None
    assert state.state == "Operational"
    assert state.attributes.get("state_class") is None

    # Verify sensor with no unit does not infer default unit or device class
    state = hass.states.get("sensor.indi_allsky_generic_temperature_sensor")
    assert state is not None
    assert state.state == "24.5"
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("unit_of_measurement") is None
    assert state.attributes.get("state_class") is None

    # Verify lamp_status does not incorrectly match 'amp' substring
    state = hass.states.get("sensor.indi_allsky_dome_lamp_status")
    assert state is not None
    assert state.state == "Off"
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("state_class") is None
    assert state.attributes.get("unit_of_measurement") is None

    # Verify subsequent scalar update preserves previously discovered metadata
    scalar_update = SensorData.from_dict(
        {
            "sensors": {
                "sensor_a_temperature": 21.0,
            }
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(scalar_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_sht4x_i2c_sht40_temperature")
    assert state is not None
    assert state.state == "21.0"
    assert state.attributes.get("unit_of_measurement") == "°C"
    assert state.attributes.get("device_class") == "temperature"
    assert state.attributes.get("state_class") == "measurement"

    # Verify subsequent value-only dictionary update preserves previously discovered metadata
    value_only_dict_update = SensorData.from_dict(
        {
            "sensors": {
                "sensor_a_temperature": {"value": 22.5},
            }
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(value_only_dict_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_sht4x_i2c_sht40_temperature")
    assert state is not None
    assert state.state == "22.5"
    assert state.attributes.get("unit_of_measurement") == "°C"
    assert state.attributes.get("device_class") == "temperature"
    assert state.attributes.get("state_class") == "measurement"

    # Verify unit-only update clears cached value so old reading is not relabeled in new unit
    unit_only_update = SensorData.from_dict(
        {
            "sensors": {
                "sensor_a_temperature": {"unit": "°F"},
            }
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(unit_only_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_sht4x_i2c_sht40_temperature")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("unit_of_measurement") == "°C"
    assert state.attributes.get("device_class") == "temperature"

    # Verify incompatible unit update clears device_class and refreshes cached user unit options
    entity_registry.async_update_entity_options(
        "sensor.indi_allsky_sht4x_i2c_sht40_temperature",
        "sensor",
        {"unit_of_measurement": "°C"},
    )
    await hass.async_block_till_done()

    incompatible_unit_update = SensorData.from_dict(
        {
            "sensors": {
                "sensor_a_temperature": {"value": 100.0, "unit": "rpm"},
            }
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(incompatible_unit_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_sht4x_i2c_sht40_temperature")
    assert state is not None
    assert state.state == "100.0"
    assert state.attributes.get("unit_of_measurement") == "rpm"
    assert state.attributes.get("device_class") is None

    # Restore °C metadata and verify explicit None value transitions state to unknown
    restore_celsius_update = SensorData.from_dict(
        {
            "sensors": {
                "sensor_a_temperature": {
                    "value": 22.5,
                    "unit": "°C",
                    "device_class": "temperature",
                },
            }
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(restore_celsius_update)
    await hass.async_block_till_done()

    # Verify explicit None value in dictionary update transitions state to unknown while retaining metadata
    null_value_dict_update = SensorData.from_dict(
        {
            "sensors": {
                "sensor_a_temperature": {"value": None},
            }
        }
    )
    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(null_value_dict_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.indi_allsky_sht4x_i2c_sht40_temperature")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("unit_of_measurement") == "°C"
    assert state.attributes.get("device_class") == "temperature"
    assert state.attributes.get("state_class") == "measurement"


async def test_initial_sensor_fetch_preserved(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: SensorData,
) -> None:
    """Test initial sensor fetch result is preserved during setup before websocket stream."""

    def _fetch_sensors_side_effect() -> bool:
        for cb in mock_indi_allsky_client.callbacks.get("sensor_update", []):
            cb(mock_sensor_data)
        return True

    mock_indi_allsky_client.fetch_sensors.side_effect = _fetch_sensors_side_effect

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Ambient temperature and dew point should be immediately present
    state = hass.states.get("sensor.indi_allsky_ambient_temperature")
    assert state is not None
    assert state.state == "21.5"

    state = hass.states.get("sensor.indi_allsky_dew_point")
    assert state is not None
    assert state.state == "14.8"


async def test_exposure_complete_triggers_sensor_fetch_and_queues_trailing(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_exposure_data: ExposureData,
) -> None:
    """Test that exposure_complete event triggers sensor fetch and queues one trailing fetch if in-flight."""
    fetch_started = asyncio.Event()
    unblock_fetch = asyncio.Event()

    async def _slow_fetch() -> None:
        fetch_started.set()
        await unblock_fetch.wait()

    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_sensors.reset_mock()
    mock_indi_allsky_client.fetch_sensors.side_effect = _slow_fetch
    fetch_started.clear()
    unblock_fetch.clear()

    callbacks = mock_indi_allsky_client.callbacks.get("exposure_complete", [])
    assert callbacks
    for cb in callbacks:
        cb(mock_exposure_data)

    await fetch_started.wait()

    # While first fetch is in flight, fire multiple exposure completes
    for cb in callbacks:
        cb(mock_exposure_data)
        cb(mock_exposure_data)

    # Let the first fetch finish; second fetch should run and then complete
    mock_indi_allsky_client.fetch_sensors.side_effect = None
    unblock_fetch.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_indi_allsky_client.fetch_sensors.call_count == 2


async def test_periodic_sensor_polling(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test periodic fallback sensor polling via time interval tracker."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_sensors.reset_mock()

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_indi_allsky_client.fetch_sensors.assert_called_once()


async def test_periodic_sensor_polling_disabled(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test periodic fallback sensor polling is not scheduled when pref_disable_polling is true."""
    entry = MockConfigEntry(
        domain="indi_allsky",
        title="INDI Allsky",
        data={
            "host": "127.0.0.1",
            "port": 443,
            "ssl": True,
            "verify_ssl": True,
        },
        entry_id="disabled_polling_entry_id",
        pref_disable_polling=True,
    )
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, entry)

    mock_indi_allsky_client.fetch_sensors.reset_mock()

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_indi_allsky_client.fetch_sensors.assert_not_called()


async def test_dynamic_sensor_edge_cases(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_exposure_data: ExposureData,
) -> None:
    """Test dynamic sensor edge cases for native_value, metadata, and timestamps."""
    with patch("homeassistant.components.indi_allsky._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    dynamic_data = SensorData.from_dict(
        {
            "sensors": {
                "custom_wind_direction": {
                    "name": "Custom Wind Direction",
                    "value": 180.0,
                    "unit": "°",
                    "device_class": "wind_direction",
                },
                "corrupted_temp": {
                    "name": "Corrupted Temp",
                    "value": "invalid_number",
                    "unit": "°C",
                    "device_class": "temperature",
                },
            }
        }
    )

    for callback in mock_indi_allsky_client.callbacks.get("sensor_update", []):
        callback(dynamic_data)
    await hass.async_block_till_done()

    # Verify wind_direction state_class measurement_angle
    state = hass.states.get("sensor.indi_allsky_custom_wind_direction")
    assert state is not None
    assert state.state == "180.0"
    assert state.attributes.get("state_class") == "measurement_angle"

    # Verify corrupted temp with state_class returns None (state unknown)
    state = hass.states.get("sensor.indi_allsky_corrupted_temp")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Now simulate coordinator having sensor missing from sensors dict
    coordinator = mock_config_entry.runtime_data
    coordinator.data = replace(
        coordinator.data, sensor=SensorData.from_dict({"sensors": {}})
    )
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.indi_allsky_custom_wind_direction")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Now simulate coordinator having sensor = None
    coordinator.data = replace(coordinator.data, sensor=None)
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.indi_allsky_custom_wind_direction")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Now simulate coordinator having sensor with sensors not a dict
    coordinator.data = replace(
        coordinator.data,
        sensor=replace(dynamic_data, sensors=None),  # type: ignore[arg-type]
    )
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.indi_allsky_custom_wind_direction")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Now test _parse_timestamp with timezone-aware datetime string
    ts_data = IndiAllSkyData(
        exposure=replace(mock_exposure_data, create_date="2026-10-22T01:00:00+02:00")
    )
    ts = _parse_timestamp(ts_data)
    assert ts is not None
    assert ts.tzinfo == dt_util.UTC
