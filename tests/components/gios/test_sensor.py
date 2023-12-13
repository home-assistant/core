"""Test sensor of GIOS integration."""
from datetime import timedelta
import json
from unittest.mock import patch

from gios import ApiError

from homeassistant.components.gios.const import ATTRIBUTION, DOMAIN
from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    DOMAIN as PLATFORM,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import init_integration

from tests.common import async_fire_time_changed, load_fixture


async def test_sensor(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test states of the sensor."""
    await init_integration(hass)

    state = hass.states.get("sensor.home_benzene")
    assert state
    assert state.state == "0.23789"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:molecule"

    entry = entity_registry.async_get("sensor.home_benzene")
    assert entry
    assert entry.unique_id == "123-c6h6"

    state = hass.states.get("sensor.home_carbon_monoxide")
    assert state
    assert state.state == "251.874"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = entity_registry.async_get("sensor.home_carbon_monoxide")
    assert entry
    assert entry.unique_id == "123-co"

    state = hass.states.get("sensor.home_nitrogen_dioxide")
    assert state
    assert state.state == "7.13411"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.NITROGEN_DIOXIDE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = entity_registry.async_get("sensor.home_nitrogen_dioxide")
    assert entry
    assert entry.unique_id == "123-no2"

    state = hass.states.get("sensor.home_nitrogen_dioxide_index")
    assert state
    assert state.state == "good"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_OPTIONS) == [
        "very_bad",
        "bad",
        "sufficient",
        "moderate",
        "good",
        "very_good",
    ]

    entry = entity_registry.async_get("sensor.home_nitrogen_dioxide_index")
    assert entry
    assert entry.unique_id == "123-no2-index"

    state = hass.states.get("sensor.home_ozone")
    assert state
    assert state.state == "95.7768"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.OZONE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = entity_registry.async_get("sensor.home_ozone")
    assert entry
    assert entry.unique_id == "123-o3"

    state = hass.states.get("sensor.home_ozone_index")
    assert state
    assert state.state == "good"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_OPTIONS) == [
        "very_bad",
        "bad",
        "sufficient",
        "moderate",
        "good",
        "very_good",
    ]

    entry = entity_registry.async_get("sensor.home_ozone_index")
    assert entry
    assert entry.unique_id == "123-o3-index"

    state = hass.states.get("sensor.home_pm10")
    assert state
    assert state.state == "16.8344"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM10
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = entity_registry.async_get("sensor.home_pm10")
    assert entry
    assert entry.unique_id == "123-pm10"

    state = hass.states.get("sensor.home_pm10_index")
    assert state
    assert state.state == "good"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_OPTIONS) == [
        "very_bad",
        "bad",
        "sufficient",
        "moderate",
        "good",
        "very_good",
    ]

    entry = entity_registry.async_get("sensor.home_pm10_index")
    assert entry
    assert entry.unique_id == "123-pm10-index"

    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == "4"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM25
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = entity_registry.async_get("sensor.home_pm2_5")
    assert entry
    assert entry.unique_id == "123-pm25"

    state = hass.states.get("sensor.home_pm2_5_index")
    assert state
    assert state.state == "good"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_OPTIONS) == [
        "very_bad",
        "bad",
        "sufficient",
        "moderate",
        "good",
        "very_good",
    ]

    entry = entity_registry.async_get("sensor.home_pm2_5_index")
    assert entry
    assert entry.unique_id == "123-pm25-index"

    state = hass.states.get("sensor.home_sulphur_dioxide")
    assert state
    assert state.state == "4.35478"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.SULPHUR_DIOXIDE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    entry = entity_registry.async_get("sensor.home_sulphur_dioxide")
    assert entry
    assert entry.unique_id == "123-so2"

    state = hass.states.get("sensor.home_sulphur_dioxide_index")
    assert state
    assert state.state == "very_good"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_OPTIONS) == [
        "very_bad",
        "bad",
        "sufficient",
        "moderate",
        "good",
        "very_good",
    ]

    entry = entity_registry.async_get("sensor.home_sulphur_dioxide_index")
    assert entry
    assert entry.unique_id == "123-so2-index"

    state = hass.states.get("sensor.home_air_quality_index")
    assert state
    assert state.state == "good"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_OPTIONS) == [
        "very_bad",
        "bad",
        "sufficient",
        "moderate",
        "good",
        "very_good",
    ]

    entry = entity_registry.async_get("sensor.home_air_quality_index")
    assert entry
    assert entry.unique_id == "123-aqi"


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    indexes = json.loads(load_fixture("gios/indexes.json"))
    sensors = json.loads(load_fixture("gios/sensors.json"))

    await init_integration(hass)

    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == "4"

    state = hass.states.get("sensor.home_pm2_5_index")
    assert state
    assert state.state == "good"

    state = hass.states.get("sensor.home_air_quality_index")
    assert state
    assert state.state == "good"

    future = utcnow() + timedelta(minutes=60)
    with patch(
        "homeassistant.components.gios.Gios._get_all_sensors",
        side_effect=ApiError("Unexpected error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_pm2_5")
        assert state
        assert state.state == STATE_UNAVAILABLE

        state = hass.states.get("sensor.home_pm2_5_index")
        assert state
        assert state.state == STATE_UNAVAILABLE

        state = hass.states.get("sensor.home_air_quality_index")
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=120)
    with patch(
        "homeassistant.components.gios.Gios._get_all_sensors",
        return_value=sensors,
    ), patch(
        "homeassistant.components.gios.Gios._get_indexes",
        return_value={},
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_pm2_5")
        assert state
        assert state.state == "4"

        # Indexes are empty so the state should be unavailable
        state = hass.states.get("sensor.home_air_quality_index")
        assert state
        assert state.state == STATE_UNAVAILABLE

        # Indexes are empty so the state should be unavailable
        state = hass.states.get("sensor.home_pm2_5_index")
        assert state
        assert state.state == STATE_UNAVAILABLE

        future = utcnow() + timedelta(minutes=180)
    with patch(
        "homeassistant.components.gios.Gios._get_all_sensors", return_value=sensors
    ), patch(
        "homeassistant.components.gios.Gios._get_indexes",
        return_value=indexes,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_pm2_5")
        assert state
        assert state.state == "4"

        state = hass.states.get("sensor.home_pm2_5_index")
        assert state
        assert state.state == "good"

        state = hass.states.get("sensor.home_air_quality_index")
        assert state
        assert state.state == "good"


async def test_invalid_indexes(hass: HomeAssistant) -> None:
    """Test states of the sensor when API returns invalid indexes."""
    await init_integration(hass, invalid_indexes=True)

    state = hass.states.get("sensor.home_nitrogen_dioxide_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_ozone_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_pm10_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_pm2_5_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_sulphur_dioxide_index")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.home_air_quality_index")
    assert state is None


async def test_unique_id_migration(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test states of the unique_id migration."""
    entity_registry.async_get_or_create(
        PLATFORM,
        DOMAIN,
        "123-pm2.5",
        suggested_object_id="home_pm2_5",
        disabled_by=None,
    )

    await init_integration(hass)

    entry = entity_registry.async_get("sensor.home_pm2_5")
    assert entry
    assert entry.unique_id == "123-pm25"
