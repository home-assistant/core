"""Test different accessory types: Sensors."""
from homeassistant.components.homekit.const import (
    ATTR_NITROGEN_DIOXIDE_DENSITY,
    ATTR_PM_2_5_DENSITY,
    ATTR_PM_10_DENSITY,
    ATTR_PM_DENSITY,
    ATTR_PM_SIZE,
    ATTR_VOC_DENSITY,
    CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5,
    CHAR_VALUE_AIR_PARTICULATE_SIZE_PM10,
    PROP_CELSIUS,
    THRESHOLD_CO,
    THRESHOLD_CO2,
)
from homeassistant.components.homekit.type_sensors import (
    BINARY_SENSOR_SERVICE_MAP,
    AirQualitySensor,
    BinarySensor,
    CarbonDioxideSensor,
    CarbonMonoxideSensor,
    HumiditySensor,
    LightSensor,
    TemperatureSensor,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)


async def test_temperature(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.temperature"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = TemperatureSensor(hass, hk_driver, "Temperature", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_temp.value == 0.0
    for key, value in PROP_CELSIUS.items():
        assert acc.char_temp.properties[key] == value

    hass.states.async_set(
        entity_id, STATE_UNKNOWN, {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}
    )
    await hass.async_block_till_done()
    assert acc.char_temp.value == 0.0

    hass.states.async_set(entity_id, "20", {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_temp.value == 20

    hass.states.async_set(
        entity_id, "75.2", {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT}
    )
    await hass.async_block_till_done()
    assert acc.char_temp.value == 24


async def test_humidity(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.humidity"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = HumiditySensor(hass, hk_driver, "Humidity", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_humidity.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_humidity.value == 0

    hass.states.async_set(entity_id, "20")
    await hass.async_block_till_done()
    assert acc.char_humidity.value == 20


async def test_air_quality_pm25(hass, hk_driver):
    """Test origional pm25 air quality sensor logic. Test if accessory is updated after state change."""
    entity_id = "sensor.pm25"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_particulate_density.value == 0
    assert acc.char_air_quality.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_particulate_density.value == 0
    assert acc.char_air_quality.value == 0

    hass.states.async_set(entity_id, "34")
    await hass.async_block_till_done()
    assert acc.char_particulate_density.value == 34
    assert acc.char_air_quality.value == 1

    hass.states.async_set(entity_id, "200")
    await hass.async_block_till_done()
    assert acc.char_particulate_density.value == 200
    assert acc.char_air_quality.value == 5


async def test_air_quality_all_props_update_all_props(hass, hk_driver):
    """Test air quality sensor with all properties is updated after state change of all properties."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(
        entity_id,
        5,
        {
            ATTR_NITROGEN_DIOXIDE_DENSITY: 10,
            ATTR_PM_2_5_DENSITY: 20,
            ATTR_PM_10_DENSITY: 30,
            ATTR_PM_DENSITY: 40,
            ATTR_PM_SIZE: 2.5,
            ATTR_VOC_DENSITY: 60,
        },
    )
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    # test initial values are all blank
    assert acc.char_air_quality.value == 0
    assert acc.char_nitrogen_dioxide_density.value == 0
    assert acc.char_pm_2_5_density.value == 0
    assert acc.char_pm_10_density.value == 0
    assert acc.char_particulate_density.value == 0
    assert acc.char_particulate_size.value == CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5
    assert acc.char_voc_density.value == 0

    # test initial set of values
    hass.states.async_set(
        entity_id,
        5,
        {
            ATTR_NITROGEN_DIOXIDE_DENSITY: 10,
            ATTR_PM_2_5_DENSITY: 20,
            ATTR_PM_10_DENSITY: 30,
            ATTR_PM_DENSITY: 40,
            ATTR_PM_SIZE: 2.5,
            ATTR_VOC_DENSITY: 60,
        },
    )
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert acc.char_nitrogen_dioxide_density.value == 10
    assert acc.char_pm_2_5_density.value == 20
    assert acc.char_pm_10_density.value == 30
    assert acc.char_particulate_density.value == 40
    assert acc.char_particulate_size.value == CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5
    assert acc.char_voc_density.value == 60

    # test changing all values
    hass.states.async_set(
        entity_id,
        1,
        {
            ATTR_NITROGEN_DIOXIDE_DENSITY: 1,
            ATTR_PM_2_5_DENSITY: 2,
            ATTR_PM_10_DENSITY: 3,
            ATTR_PM_DENSITY: 4,
            ATTR_PM_SIZE: 10,
            ATTR_VOC_DENSITY: 6,
        },
    )
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 1
    assert acc.char_nitrogen_dioxide_density.value == 1
    assert acc.char_pm_2_5_density.value == 2
    assert acc.char_pm_10_density.value == 3
    assert acc.char_particulate_density.value == 4
    assert acc.char_particulate_size.value == CHAR_VALUE_AIR_PARTICULATE_SIZE_PM10
    assert acc.char_voc_density.value == 6


async def test_air_quality_all_props_update_one_prop(hass, hk_driver):
    """Test air quality sensor with all properties is updated after state change of one propety."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(
        entity_id,
        5,
        {
            ATTR_NITROGEN_DIOXIDE_DENSITY: 10,
            ATTR_PM_2_5_DENSITY: 20,
            ATTR_PM_10_DENSITY: 30,
            ATTR_PM_DENSITY: 40,
            ATTR_PM_SIZE: 2.5,
            ATTR_VOC_DENSITY: 60,
        },
    )
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    # test initial values are all blank
    assert acc.char_air_quality.value == 0
    assert acc.char_nitrogen_dioxide_density.value == 0
    assert acc.char_pm_2_5_density.value == 0
    assert acc.char_pm_10_density.value == 0
    assert acc.char_particulate_density.value == 0
    assert acc.char_particulate_size.value == CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5
    assert acc.char_voc_density.value == 0

    # test initial set of values
    hass.states.async_set(
        entity_id,
        5,
        {
            ATTR_NITROGEN_DIOXIDE_DENSITY: 10,
            ATTR_PM_2_5_DENSITY: 20,
            ATTR_PM_10_DENSITY: 30,
            ATTR_PM_DENSITY: 40,
            ATTR_PM_SIZE: 2.5,
            ATTR_VOC_DENSITY: 60,
        },
    )
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert acc.char_nitrogen_dioxide_density.value == 10
    assert acc.char_pm_2_5_density.value == 20
    assert acc.char_pm_10_density.value == 30
    assert acc.char_particulate_density.value == 40
    assert acc.char_particulate_size.value == CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5
    assert acc.char_voc_density.value == 60

    # test changing one value
    hass.states.async_set(entity_id, 5, {ATTR_NITROGEN_DIOXIDE_DENSITY: 1})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert acc.char_nitrogen_dioxide_density.value == 1
    assert acc.char_pm_2_5_density.value == 20
    assert acc.char_pm_10_density.value == 30
    assert acc.char_particulate_density.value == 40
    assert acc.char_particulate_size.value == CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5
    assert acc.char_voc_density.value == 60


async def test_air_quality_state_only(hass, hk_driver):
    """Test air quality sensor with only state is updated after state change."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(entity_id, 5, {})
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    # test initial values are all blank
    assert acc.char_air_quality.value == 0
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test initial set of values
    hass.states.async_set(entity_id, 5, {})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test changing value
    hass.states.async_set(entity_id, 4, {})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 4
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")


async def test_air_quality_state_and_nitrogen_dioxide_density(hass, hk_driver):
    """Test air quality sensor with only state and nitrogen dioxide density is updated after state change."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(entity_id, 5, {ATTR_NITROGEN_DIOXIDE_DENSITY: 1})
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    # test initial values are all blank
    assert acc.char_air_quality.value == 0
    assert acc.char_nitrogen_dioxide_density.value == 0
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test initial set of values
    hass.states.async_set(entity_id, 5, {ATTR_NITROGEN_DIOXIDE_DENSITY: 1})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert acc.char_nitrogen_dioxide_density.value == 1
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test changing value
    hass.states.async_set(entity_id, 5, {ATTR_NITROGEN_DIOXIDE_DENSITY: 10})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert acc.char_nitrogen_dioxide_density.value == 10
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")


async def test_air_quality_state_and_pm_2_5_density_only(hass, hk_driver):
    """Test air quality sensor with only state and pm 2.5 density is updated after state change."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(entity_id, 5, {ATTR_PM_2_5_DENSITY: 2})
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    # test initial values are all blank
    assert acc.char_air_quality.value == 0
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert acc.char_pm_2_5_density.value == 0
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test initial set of values
    hass.states.async_set(entity_id, 5, {ATTR_PM_2_5_DENSITY: 2})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert acc.char_pm_2_5_density.value == 2
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test changing value
    hass.states.async_set(entity_id, 5, {ATTR_PM_2_5_DENSITY: 20})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert acc.char_pm_2_5_density.value == 20
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")


async def test_air_quality_state_and_pm_10_density_only(hass, hk_driver):
    """Test air quality sensor with only state and pm 10 density is updated after state change."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(entity_id, 5, {ATTR_PM_10_DENSITY: 3})
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    # test initial values are all blank
    assert acc.char_air_quality.value == 0
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert acc.char_pm_10_density.value == 0
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test initial set of values
    hass.states.async_set(entity_id, 5, {ATTR_PM_10_DENSITY: 3})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert acc.char_pm_10_density.value == 3
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test changing value
    hass.states.async_set(entity_id, 5, {ATTR_PM_10_DENSITY: 30})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert acc.char_pm_10_density.value == 30
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")


async def test_air_quality_state_and_particulate_density_only(hass, hk_driver):
    """Test air quality sensor with only state and particulate density is updated after state change."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(entity_id, 5, {ATTR_PM_DENSITY: 4})
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    # test initial values are all blank
    assert acc.char_air_quality.value == 0
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert acc.char_particulate_density.value == 0
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test initial set of values
    hass.states.async_set(entity_id, 5, {ATTR_PM_DENSITY: 4})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert acc.char_particulate_density.value == 4
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")

    # test changing value
    hass.states.async_set(entity_id, 5, {ATTR_PM_DENSITY: 40})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert acc.char_particulate_density.value == 40
    assert not hasattr(acc, "char_particulate_size")
    assert not hasattr(acc, "char_voc_density")


async def test_air_quality_state_and_particulate_size_only(hass, hk_driver):
    """Test air quality sensor with only state and particulate size is updated after state change."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(entity_id, 5, {ATTR_PM_SIZE: 2.5})
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    # test initial values are all blank
    assert acc.char_air_quality.value == 0
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert acc.char_particulate_size.value == CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5
    assert not hasattr(acc, "char_voc_density")

    # test initial set of values
    hass.states.async_set(entity_id, 5, {ATTR_PM_SIZE: 2.5})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert acc.char_particulate_size.value == CHAR_VALUE_AIR_PARTICULATE_SIZE_PM2_5
    assert not hasattr(acc, "char_voc_density")

    # test changing value
    hass.states.async_set(entity_id, 5, {ATTR_PM_SIZE: 10})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert acc.char_particulate_size.value == CHAR_VALUE_AIR_PARTICULATE_SIZE_PM10
    assert not hasattr(acc, "char_voc_density")


async def test_air_quality_state_and_voc_density_only(hass, hk_driver):
    """Test air quality sensor with only state and voc density is updated after state change."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(entity_id, 5, {ATTR_VOC_DENSITY: 6})
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    # test initial values are all blank
    assert acc.char_air_quality.value == 0
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert acc.char_voc_density.value == 0

    # test initial set of values
    hass.states.async_set(entity_id, 5, {ATTR_VOC_DENSITY: 6})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert acc.char_voc_density.value == 6

    # test changing value
    hass.states.async_set(entity_id, 5, {ATTR_VOC_DENSITY: 60})
    await hass.async_block_till_done()

    assert acc.char_air_quality.value == 5
    assert not hasattr(acc, "char_nitrogen_dioxide_density")
    assert not hasattr(acc, "char_pm_2_5_density")
    assert not hasattr(acc, "char_pm_10_density")
    assert not hasattr(acc, "char_particulate_density")
    assert not hasattr(acc, "char_particulate_size")
    assert acc.char_voc_density.value == 60


async def test_co(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.co"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = CarbonMonoxideSensor(hass, hk_driver, "CO", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_level.value == 0
    assert acc.char_peak.value == 0
    assert acc.char_detected.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_level.value == 0
    assert acc.char_peak.value == 0
    assert acc.char_detected.value == 0

    value = 32
    assert value > THRESHOLD_CO
    hass.states.async_set(entity_id, str(value))
    await hass.async_block_till_done()
    assert acc.char_level.value == 32
    assert acc.char_peak.value == 32
    assert acc.char_detected.value == 1

    value = 10
    assert value < THRESHOLD_CO
    hass.states.async_set(entity_id, str(value))
    await hass.async_block_till_done()
    assert acc.char_level.value == 10
    assert acc.char_peak.value == 32
    assert acc.char_detected.value == 0


async def test_co2(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.co2"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = CarbonDioxideSensor(hass, hk_driver, "CO2", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_level.value == 0
    assert acc.char_peak.value == 0
    assert acc.char_detected.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_level.value == 0
    assert acc.char_peak.value == 0
    assert acc.char_detected.value == 0

    value = 1100
    assert value > THRESHOLD_CO2
    hass.states.async_set(entity_id, str(value))
    await hass.async_block_till_done()
    assert acc.char_level.value == 1100
    assert acc.char_peak.value == 1100
    assert acc.char_detected.value == 1

    value = 800
    assert value < THRESHOLD_CO2
    hass.states.async_set(entity_id, str(value))
    await hass.async_block_till_done()
    assert acc.char_level.value == 800
    assert acc.char_peak.value == 1100
    assert acc.char_detected.value == 0


async def test_light(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.light"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = LightSensor(hass, hk_driver, "Light", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_light.value == 0.0001

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_light.value == 0.0001

    hass.states.async_set(entity_id, "300")
    await hass.async_block_till_done()
    assert acc.char_light.value == 300


async def test_binary(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "binary_sensor.opening"

    hass.states.async_set(entity_id, STATE_UNKNOWN, {ATTR_DEVICE_CLASS: "opening"})
    await hass.async_block_till_done()

    acc = BinarySensor(hass, hk_driver, "Window Opening", entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_detected.value == 0

    hass.states.async_set(entity_id, STATE_ON, {ATTR_DEVICE_CLASS: "opening"})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 1

    hass.states.async_set(entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: "opening"})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0

    hass.states.async_set(entity_id, STATE_HOME, {ATTR_DEVICE_CLASS: "opening"})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 1

    hass.states.async_set(entity_id, STATE_NOT_HOME, {ATTR_DEVICE_CLASS: "opening"})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0


async def test_binary_device_classes(hass, hk_driver):
    """Test if services and characteristics are assigned correctly."""
    entity_id = "binary_sensor.demo"

    for device_class, (service, char) in BINARY_SENSOR_SERVICE_MAP.items():
        hass.states.async_set(entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: device_class})
        await hass.async_block_till_done()

        acc = BinarySensor(hass, hk_driver, "Binary Sensor", entity_id, 2, None)
        assert acc.get_service(service).display_name == service
        assert acc.char_detected.display_name == char
