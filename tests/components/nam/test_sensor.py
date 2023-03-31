"""Test sensor of Nettigo Air Monitor integration."""
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from nettigo_air_monitor import ApiError

from homeassistant.components.nam.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNAVAILABLE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import INCOMPLETE_NAM_DATA, init_integration, nam_data

from tests.common import async_fire_time_changed


async def test_sensor(hass: HomeAssistant) -> None:
    """Test states of the air_quality."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-signal",
        suggested_object_id="nettigo_air_monitor_signal_strength",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-uptime",
        suggested_object_id="nettigo_air_monitor_uptime",
        disabled_by=None,
    )

    # Patch return value from utcnow, with offset to make sure the patch is correct
    now = utcnow() - timedelta(hours=1)
    with patch("homeassistant.components.nam.sensor.utcnow", return_value=now):
        await init_integration(hass)

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_humidity")
    assert state
    assert state.state == "45.7"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.nettigo_air_monitor_bme280_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bme280_humidity"

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state == "7.6"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_bme280_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bme280_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_pressure")
    assert state
    assert state.state == "1011.012"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.HPA

    entry = registry.async_get("sensor.nettigo_air_monitor_bme280_pressure")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bme280_pressure"

    state = hass.states.get("sensor.nettigo_air_monitor_bmp180_temperature")
    assert state
    assert state.state == "7.6"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_bmp180_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bmp180_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_bmp180_pressure")
    assert state
    assert state.state == "1032.012"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.HPA

    entry = registry.async_get("sensor.nettigo_air_monitor_bmp180_pressure")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bmp180_pressure"

    state = hass.states.get("sensor.nettigo_air_monitor_bmp280_temperature")
    assert state
    assert state.state == "5.6"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_bmp280_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bmp280_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_bmp280_pressure")
    assert state
    assert state.state == "1022.012"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PRESSURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.HPA

    entry = registry.async_get("sensor.nettigo_air_monitor_bmp280_pressure")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-bmp280_pressure"

    state = hass.states.get("sensor.nettigo_air_monitor_sht3x_humidity")
    assert state
    assert state.state == "34.7"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.nettigo_air_monitor_sht3x_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sht3x_humidity"

    state = hass.states.get("sensor.nettigo_air_monitor_sht3x_temperature")
    assert state
    assert state.state == "6.3"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_sht3x_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sht3x_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_dht22_humidity")
    assert state
    assert state.state == "46.2"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.nettigo_air_monitor_dht22_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-dht22_humidity"

    state = hass.states.get("sensor.nettigo_air_monitor_dht22_temperature")
    assert state
    assert state.state == "6.3"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_dht22_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-dht22_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_heca_humidity")
    assert state
    assert state.state == "50.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.nettigo_air_monitor_heca_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-heca_humidity"

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == "8.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    entry = registry.async_get("sensor.nettigo_air_monitor_heca_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-heca_temperature"

    state = hass.states.get("sensor.nettigo_air_monitor_signal_strength")
    assert state
    assert state.state == "-72.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.SIGNAL_STRENGTH
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )

    entry = registry.async_get("sensor.nettigo_air_monitor_signal_strength")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-signal"

    state = hass.states.get("sensor.nettigo_air_monitor_uptime")
    assert state
    assert (
        state.state
        == (now - timedelta(seconds=456987)).replace(microsecond=0).isoformat()
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert state.attributes.get(ATTR_STATE_CLASS) is None

    entry = registry.async_get("sensor.nettigo_air_monitor_uptime")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-uptime"

    state = hass.states.get("sensor.nettigo_air_monitor_pmsx003_caqi_level")
    assert state
    assert state.state == "very_low"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert state.attributes.get(ATTR_OPTIONS) == [
        "very_low",
        "low",
        "medium",
        "high",
        "very_high",
    ]
    assert state.attributes.get(ATTR_ICON) == "mdi:air-filter"

    entry = registry.async_get("sensor.nettigo_air_monitor_pmsx003_caqi_level")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-pms_caqi_level"
    assert entry.translation_key == "caqi_level"

    state = hass.states.get("sensor.nettigo_air_monitor_pmsx003_caqi")
    assert state
    assert state.state == "19"
    assert state.attributes.get(ATTR_ICON) == "mdi:air-filter"

    entry = registry.async_get("sensor.nettigo_air_monitor_pmsx003_caqi")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-pms_caqi"

    state = hass.states.get("sensor.nettigo_air_monitor_pmsx003_particulate_matter_10")
    assert state
    assert state.state == "10.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM10
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get(
        "sensor.nettigo_air_monitor_pmsx003_particulate_matter_10"
    )
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-pms_p1"

    state = hass.states.get("sensor.nettigo_air_monitor_pmsx003_particulate_matter_2_5")
    assert state
    assert state.state == "11.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM25
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get(
        "sensor.nettigo_air_monitor_pmsx003_particulate_matter_2_5"
    )
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-pms_p2"

    state = hass.states.get("sensor.nettigo_air_monitor_pmsx003_particulate_matter_1_0")
    assert state
    assert state.state == "6.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM1
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get(
        "sensor.nettigo_air_monitor_pmsx003_particulate_matter_1_0"
    )
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-pms_p0"

    state = hass.states.get("sensor.nettigo_air_monitor_sds011_particulate_matter_10")
    assert state
    assert state.state == "18.6"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM10
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get(
        "sensor.nettigo_air_monitor_sds011_particulate_matter_10"
    )
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sds011_p1"

    state = hass.states.get("sensor.nettigo_air_monitor_sds011_caqi")
    assert state
    assert state.state == "19"
    assert state.attributes.get(ATTR_ICON) == "mdi:air-filter"

    entry = registry.async_get("sensor.nettigo_air_monitor_sds011_caqi")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sds011_caqi"

    state = hass.states.get("sensor.nettigo_air_monitor_sds011_caqi_level")
    assert state
    assert state.state == "very_low"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert state.attributes.get(ATTR_OPTIONS) == [
        "very_low",
        "low",
        "medium",
        "high",
        "very_high",
    ]
    assert state.attributes.get(ATTR_ICON) == "mdi:air-filter"

    entry = registry.async_get("sensor.nettigo_air_monitor_sds011_caqi_level")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sds011_caqi_level"
    assert entry.translation_key == "caqi_level"

    state = hass.states.get("sensor.nettigo_air_monitor_sds011_particulate_matter_2_5")
    assert state
    assert state.state == "11.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM25
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get(
        "sensor.nettigo_air_monitor_sds011_particulate_matter_2_5"
    )
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sds011_p2"

    state = hass.states.get("sensor.nettigo_air_monitor_sps30_caqi")
    assert state
    assert state.state == "54"
    assert state.attributes.get(ATTR_ICON) == "mdi:air-filter"

    entry = registry.async_get("sensor.nettigo_air_monitor_sps30_caqi")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sps30_caqi"

    state = hass.states.get("sensor.nettigo_air_monitor_sps30_caqi_level")
    assert state
    assert state.state == "medium"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert state.attributes.get(ATTR_OPTIONS) == [
        "very_low",
        "low",
        "medium",
        "high",
        "very_high",
    ]
    assert state.attributes.get(ATTR_ICON) == "mdi:air-filter"

    entry = registry.async_get("sensor.nettigo_air_monitor_sps30_caqi_level")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sps30_caqi_level"
    assert entry.translation_key == "caqi_level"

    state = hass.states.get("sensor.nettigo_air_monitor_sps30_particulate_matter_1_0")
    assert state
    assert state.state == "31.2"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM1
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get(
        "sensor.nettigo_air_monitor_sps30_particulate_matter_1_0"
    )
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sps30_p0"

    state = hass.states.get("sensor.nettigo_air_monitor_sps30_particulate_matter_10")
    assert state
    assert state.state == "21.2"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM10
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get("sensor.nettigo_air_monitor_sps30_particulate_matter_10")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sps30_p1"

    state = hass.states.get("sensor.nettigo_air_monitor_sps30_particulate_matter_2_5")
    assert state
    assert state.state == "34.3"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM25
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = registry.async_get(
        "sensor.nettigo_air_monitor_sps30_particulate_matter_2_5"
    )
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sps30_p2"

    state = hass.states.get("sensor.nettigo_air_monitor_sps30_particulate_matter_4_0")
    assert state
    assert state.state == "24.7"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:molecule"

    entry = registry.async_get(
        "sensor.nettigo_air_monitor_sps30_particulate_matter_4_0"
    )
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-sps30_p4"

    state = hass.states.get("sensor.nettigo_air_monitor_mh_z14a_carbon_dioxide")
    assert state
    assert state.state == "865.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CO2
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_MILLION
    )
    entry = registry.async_get("sensor.nettigo_air_monitor_mh_z14a_carbon_dioxide")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-mhz14a_carbon_dioxide"


async def test_sensor_disabled(hass: HomeAssistant) -> None:
    """Test sensor disabled by default."""
    await init_integration(hass)
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.nettigo_air_monitor_signal_strength")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-signal"
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity
    updated_entry = registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False


async def test_incompleta_data_after_device_restart(hass: HomeAssistant) -> None:
    """Test states of the air_quality after device restart."""
    await init_integration(hass)

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == "8.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    future = utcnow() + timedelta(minutes=6)
    update_response = Mock(json=AsyncMock(return_value=INCOMPLETE_NAM_DATA))
    with patch("homeassistant.components.nam.NettigoAirMonitor.initialize"), patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_http_request",
        return_value=update_response,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_heca_temperature")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when device causes an error."""
    await init_integration(hass)

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "7.6"

    future = utcnow() + timedelta(minutes=6)
    with patch("homeassistant.components.nam.NettigoAirMonitor.initialize"), patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_http_request",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=12)
    update_response = Mock(json=AsyncMock(return_value=nam_data))
    with patch("homeassistant.components.nam.NettigoAirMonitor.initialize"), patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_http_request",
        return_value=update_response,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.nettigo_air_monitor_bme280_temperature")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "7.6"


async def test_manual_update_entity(hass: HomeAssistant) -> None:
    """Test manual update entity via service homeasasistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})

    update_response = Mock(json=AsyncMock(return_value=nam_data))
    with patch("homeassistant.components.nam.NettigoAirMonitor.initialize"), patch(
        "homeassistant.components.nam.NettigoAirMonitor._async_http_request",
        return_value=update_response,
    ) as mock_get_data:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.nettigo_air_monitor_bme280_temperature"]},
            blocking=True,
        )

    assert mock_get_data.call_count == 1


async def test_unique_id_migration(hass: HomeAssistant) -> None:
    """Test states of the unique_id migration."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-temperature",
        suggested_object_id="nettigo_air_monitor_dht22_temperature",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-humidity",
        suggested_object_id="nettigo_air_monitor_dht22_humidity",
        disabled_by=None,
    )

    await init_integration(hass)

    entry = registry.async_get("sensor.nettigo_air_monitor_dht22_temperature")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-dht22_temperature"

    entry = registry.async_get("sensor.nettigo_air_monitor_dht22_humidity")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-dht22_humidity"
