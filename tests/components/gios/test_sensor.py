"""Test sensor of GIOS integration."""
from datetime import timedelta
import json
from unittest.mock import patch

from gios import ApiError

from homeassistant.components.gios.const import (
    ATTR_INDEX,
    ATTR_STATION,
    ATTRIBUTION,
    DOMAIN,
)
from homeassistant.components.sensor import (
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


async def test_sensor(hass: HomeAssistant) -> None:
    """Test states of the sensor."""
    await init_integration(hass)
    registry = er.async_get(hass)

    state = hass.states.get("sensor.home_c6h6")
    assert state
    assert state.state == "0"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:molecule"
    assert state.attributes.get(ATTR_INDEX) == "bardzo dobry"

    entry = registry.async_get("sensor.home_c6h6")
    assert entry
    assert entry.unique_id == "123-c6h6"

    state = hass.states.get("sensor.home_co")
    assert state
    assert state.state == "252"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) == "dobry"

    entry = registry.async_get("sensor.home_co")
    assert entry
    assert entry.unique_id == "123-co"

    state = hass.states.get("sensor.home_no2")
    assert state
    assert state.state == "7"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.NITROGEN_DIOXIDE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) == "dobry"

    entry = registry.async_get("sensor.home_no2")
    assert entry
    assert entry.unique_id == "123-no2"

    state = hass.states.get("sensor.home_o3")
    assert state
    assert state.state == "96"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.OZONE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) == "dobry"

    entry = registry.async_get("sensor.home_o3")
    assert entry
    assert entry.unique_id == "123-o3"

    state = hass.states.get("sensor.home_pm10")
    assert state
    assert state.state == "17"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM10
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) == "dobry"

    entry = registry.async_get("sensor.home_pm10")
    assert entry
    assert entry.unique_id == "123-pm10"

    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == "4"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM25
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) == "dobry"

    entry = registry.async_get("sensor.home_pm2_5")
    assert entry
    assert entry.unique_id == "123-pm25"

    state = hass.states.get("sensor.home_so2")
    assert state
    assert state.state == "4"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.SULPHUR_DIOXIDE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) == "bardzo dobry"

    entry = registry.async_get("sensor.home_so2")
    assert entry
    assert entry.unique_id == "123-so2"

    state = hass.states.get("sensor.home_aqi")
    assert state
    assert state.state == "dobry"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    entry = registry.async_get("sensor.home_aqi")
    assert entry
    assert entry.unique_id == "123-aqi"


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    await init_integration(hass)

    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "4"

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

    future = utcnow() + timedelta(minutes=120)
    with patch(
        "homeassistant.components.gios.Gios._get_all_sensors",
        return_value=json.loads(load_fixture("gios/sensors.json")),
    ), patch(
        "homeassistant.components.gios.Gios._get_indexes",
        return_value={},
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_pm2_5")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "4"

        state = hass.states.get("sensor.home_aqi")
        assert state
        assert state.state == STATE_UNAVAILABLE


async def test_invalid_indexes(hass: HomeAssistant) -> None:
    """Test states of the sensor when API returns invalid indexes."""
    await init_integration(hass, invalid_indexes=True)
    registry = er.async_get(hass)

    state = hass.states.get("sensor.home_c6h6")
    assert state
    assert state.state == "0"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:molecule"
    assert state.attributes.get(ATTR_INDEX) is None

    entry = registry.async_get("sensor.home_c6h6")
    assert entry
    assert entry.unique_id == "123-c6h6"

    state = hass.states.get("sensor.home_co")
    assert state
    assert state.state == "252"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) is None

    entry = registry.async_get("sensor.home_co")
    assert entry
    assert entry.unique_id == "123-co"

    state = hass.states.get("sensor.home_no2")
    assert state
    assert state.state == "7"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) is None

    entry = registry.async_get("sensor.home_no2")
    assert entry
    assert entry.unique_id == "123-no2"

    state = hass.states.get("sensor.home_o3")
    assert state
    assert state.state == "96"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) is None

    entry = registry.async_get("sensor.home_o3")
    assert entry
    assert entry.unique_id == "123-o3"

    state = hass.states.get("sensor.home_pm10")
    assert state
    assert state.state == "17"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) is None

    entry = registry.async_get("sensor.home_pm10")
    assert entry
    assert entry.unique_id == "123-pm10"

    state = hass.states.get("sensor.home_pm2_5")
    assert state
    assert state.state == "4"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) is None

    entry = registry.async_get("sensor.home_pm2_5")
    assert entry
    assert entry.unique_id == "123-pm25"

    state = hass.states.get("sensor.home_so2")
    assert state
    assert state.state == "4"
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_STATION) == "Test Name 1"
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_INDEX) is None

    entry = registry.async_get("sensor.home_so2")
    assert entry
    assert entry.unique_id == "123-so2"

    state = hass.states.get("sensor.home_aqi")
    assert state is None


async def test_aqi_sensor_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the AQI sensor unavailable correctly when indexes are invalid."""
    await init_integration(hass)

    state = hass.states.get("sensor.home_aqi")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "dobry"

    future = utcnow() + timedelta(minutes=60)
    with patch(
        "homeassistant.components.gios.Gios._get_all_sensors",
        return_value=json.loads(load_fixture("gios/sensors.json")),
    ), patch(
        "homeassistant.components.gios.Gios._get_indexes",
        return_value={},
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_aqi")
        assert state
        assert state.state == STATE_UNAVAILABLE


async def test_unique_id_migration(hass: HomeAssistant) -> None:
    """Test states of the unique_id migration."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        PLATFORM,
        DOMAIN,
        "123-pm2.5",
        suggested_object_id="home_pm2_5",
        disabled_by=None,
    )

    await init_integration(hass)

    entry = registry.async_get("sensor.home_pm2_5")
    assert entry
    assert entry.unique_id == "123-pm25"
