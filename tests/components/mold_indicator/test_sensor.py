"""The tests for the MoldIndicator sensor."""

import pytest

from homeassistant.components import sensor
from homeassistant.components.mold_indicator.sensor import (
    ATTR_CRITICAL_TEMP,
    ATTR_DEWPOINT,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def init_sensors_fixture(hass: HomeAssistant) -> None:
    """Set up things to be run when tests are started."""
    hass.states.async_set(
        "test.indoortemp", "20", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set(
        "test.outdoortemp", "10", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set(
        "test.indoorhumidity", "50", {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )


async def test_setup(hass: HomeAssistant) -> None:
    """Test the mold indicator sensor setup."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "mold_indicator",
                "indoor_temp_sensor": "test.indoortemp",
                "outdoor_temp_sensor": "test.outdoortemp",
                "indoor_humidity_sensor": "test.indoorhumidity",
                "calibration_factor": 2.0,
            }
        },
    )
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_setup_from_config_entry(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test the mold indicator sensor setup from a config entry."""

    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_invalidcalib(hass: HomeAssistant) -> None:
    """Test invalid sensor values."""
    hass.states.async_set(
        "test.indoortemp", "10", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set(
        "test.outdoortemp", "10", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set(
        "test.indoorhumidity", "0", {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )

    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "mold_indicator",
                "indoor_temp_sensor": "test.indoortemp",
                "outdoor_temp_sensor": "test.outdoortemp",
                "indoor_humidity_sensor": "test.indoorhumidity",
                "calibration_factor": 0,
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.state == "unavailable"
    assert moldind.attributes.get(ATTR_DEWPOINT) is None
    assert moldind.attributes.get(ATTR_CRITICAL_TEMP) is None


async def test_invalidhum(hass: HomeAssistant) -> None:
    """Test invalid sensor values."""
    hass.states.async_set(
        "test.indoortemp", "10", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set(
        "test.outdoortemp", "10", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set(
        "test.indoorhumidity", "-1", {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )

    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "mold_indicator",
                "indoor_temp_sensor": "test.indoortemp",
                "outdoor_temp_sensor": "test.outdoortemp",
                "indoor_humidity_sensor": "test.indoorhumidity",
                "calibration_factor": 2.0,
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.state == "unavailable"
    assert moldind.attributes.get(ATTR_DEWPOINT) is None
    assert moldind.attributes.get(ATTR_CRITICAL_TEMP) is None

    hass.states.async_set(
        "test.indoorhumidity", "A", {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.state == "unavailable"
    assert moldind.attributes.get(ATTR_DEWPOINT) is None
    assert moldind.attributes.get(ATTR_CRITICAL_TEMP) is None

    hass.states.async_set(
        "test.indoorhumidity",
        "10",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.state == "unavailable"
    assert moldind.attributes.get(ATTR_DEWPOINT) is None
    assert moldind.attributes.get(ATTR_CRITICAL_TEMP) is None


async def test_calculation(hass: HomeAssistant) -> None:
    """Test the mold indicator internal calculations."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "mold_indicator",
                "indoor_temp_sensor": "test.indoortemp",
                "outdoor_temp_sensor": "test.outdoortemp",
                "indoor_humidity_sensor": "test.indoorhumidity",
                "calibration_factor": 2.0,
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind

    # assert dewpoint
    dewpoint = moldind.attributes.get(ATTR_DEWPOINT)
    assert dewpoint
    assert dewpoint > 9.2
    assert dewpoint < 9.3

    # assert temperature estimation
    esttemp = moldind.attributes.get(ATTR_CRITICAL_TEMP)
    assert esttemp
    assert esttemp > 14.9
    assert esttemp < 15.1

    # assert mold indicator value
    state = moldind.state
    assert state
    assert state == "68"


async def test_unknown_sensor(hass: HomeAssistant) -> None:
    """Test the sensor_changed function."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "mold_indicator",
                "indoor_temp_sensor": "test.indoortemp",
                "outdoor_temp_sensor": "test.outdoortemp",
                "indoor_humidity_sensor": "test.indoorhumidity",
                "calibration_factor": 2.0,
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()

    hass.states.async_set(
        "test.indoortemp",
        STATE_UNKNOWN,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.state == "unavailable"
    assert moldind.attributes.get(ATTR_DEWPOINT) is None
    assert moldind.attributes.get(ATTR_CRITICAL_TEMP) is None

    hass.states.async_set(
        "test.indoortemp", "30", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set(
        "test.outdoortemp",
        STATE_UNKNOWN,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.state == "unavailable"
    assert moldind.attributes.get(ATTR_DEWPOINT) is None
    assert moldind.attributes.get(ATTR_CRITICAL_TEMP) is None

    hass.states.async_set(
        "test.outdoortemp", "25", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    hass.states.async_set(
        "test.indoorhumidity",
        STATE_UNKNOWN,
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE},
    )
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.state == "unavailable"
    assert moldind.attributes.get(ATTR_DEWPOINT) is None
    assert moldind.attributes.get(ATTR_CRITICAL_TEMP) is None

    hass.states.async_set(
        "test.indoorhumidity", "20", {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )
    await hass.async_block_till_done()
    moldind = hass.states.get("sensor.mold_indicator")
    assert moldind
    assert moldind.state == "23"

    dewpoint = moldind.attributes.get(ATTR_DEWPOINT)
    assert dewpoint
    assert dewpoint > 4.5
    assert dewpoint < 4.6

    esttemp = moldind.attributes.get(ATTR_CRITICAL_TEMP)
    assert esttemp
    assert esttemp == 27.5


async def test_sensor_changed(hass: HomeAssistant) -> None:
    """Test the sensor_changed function."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "mold_indicator",
                "indoor_temp_sensor": "test.indoortemp",
                "outdoor_temp_sensor": "test.outdoortemp",
                "indoor_humidity_sensor": "test.indoorhumidity",
                "calibration_factor": 2.0,
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()

    hass.states.async_set(
        "test.indoortemp", "30", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mold_indicator").state == "90"

    hass.states.async_set(
        "test.outdoortemp", "25", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mold_indicator").state == "57"

    hass.states.async_set(
        "test.indoorhumidity", "20", {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mold_indicator").state == "23"
