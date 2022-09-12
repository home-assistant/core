"""Test different accessory types: Sensors."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.homekit import get_accessory
from homeassistant.components.homekit.const import (
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
    PM10Sensor,
    PM25Sensor,
    TemperatureSensor,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
    PERCENTAGE,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import CoreState
from homeassistant.helpers import entity_registry as er


async def test_temperature(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.temperature"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = TemperatureSensor(hass, hk_driver, "Temperature", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

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

    hass.states.async_set(entity_id, "0", {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_temp.value == 0

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
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_humidity.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_humidity.value == 0

    hass.states.async_set(entity_id, "20")
    await hass.async_block_till_done()
    assert acc.char_humidity.value == 20

    hass.states.async_set(entity_id, "0")
    await hass.async_block_till_done()
    assert acc.char_humidity.value == 0


async def test_air_quality(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, "34")
    await hass.async_block_till_done()
    assert acc.char_density.value == 34
    assert acc.char_quality.value == 2

    hass.states.async_set(entity_id, "200")
    await hass.async_block_till_done()
    assert acc.char_density.value == 200
    assert acc.char_quality.value == 5


async def test_pm10(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.air_quality_pm10"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = PM10Sensor(hass, hk_driver, "PM10 Sensor", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, "34")
    await hass.async_block_till_done()
    assert acc.char_density.value == 34
    assert acc.char_quality.value == 1

    hass.states.async_set(entity_id, "70")
    await hass.async_block_till_done()
    assert acc.char_density.value == 70
    assert acc.char_quality.value == 2

    hass.states.async_set(entity_id, "110")
    await hass.async_block_till_done()
    assert acc.char_density.value == 110
    assert acc.char_quality.value == 3

    hass.states.async_set(entity_id, "200")
    await hass.async_block_till_done()
    assert acc.char_density.value == 200
    assert acc.char_quality.value == 4

    hass.states.async_set(entity_id, "400")
    await hass.async_block_till_done()
    assert acc.char_density.value == 400
    assert acc.char_quality.value == 5


async def test_pm25(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.air_quality_pm25"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = PM25Sensor(hass, hk_driver, "PM25 Sensor", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, "23")
    await hass.async_block_till_done()
    assert acc.char_density.value == 23
    assert acc.char_quality.value == 2

    hass.states.async_set(entity_id, "34")
    await hass.async_block_till_done()
    assert acc.char_density.value == 34
    assert acc.char_quality.value == 2

    hass.states.async_set(entity_id, "90")
    await hass.async_block_till_done()
    assert acc.char_density.value == 90
    assert acc.char_quality.value == 4

    hass.states.async_set(entity_id, "200")
    await hass.async_block_till_done()
    assert acc.char_density.value == 200
    assert acc.char_quality.value == 5

    hass.states.async_set(entity_id, "400")
    await hass.async_block_till_done()
    assert acc.char_density.value == 400
    assert acc.char_quality.value == 5


async def test_co(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "sensor.co"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = CarbonMonoxideSensor(hass, hk_driver, "CO", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

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
    await acc.run()
    await hass.async_block_till_done()

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
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_light.value == 0.0001

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_light.value == 0.0001

    hass.states.async_set(entity_id, "300")
    await hass.async_block_till_done()
    assert acc.char_light.value == 300

    hass.states.async_set(entity_id, "0")
    await hass.async_block_till_done()
    assert acc.char_light.value == 0.0001


async def test_binary(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "binary_sensor.opening"

    hass.states.async_set(entity_id, STATE_UNKNOWN, {ATTR_DEVICE_CLASS: "opening"})
    await hass.async_block_till_done()

    acc = BinarySensor(hass, hk_driver, "Window Opening", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

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


async def test_motion_uses_bool(hass, hk_driver):
    """Test if accessory is updated after state change."""
    entity_id = "binary_sensor.motion"

    hass.states.async_set(
        entity_id, STATE_UNKNOWN, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()

    acc = BinarySensor(hass, hk_driver, "Motion Sensor", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_detected.value is False

    hass.states.async_set(
        entity_id, STATE_ON, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert acc.char_detected.value is True

    hass.states.async_set(
        entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert acc.char_detected.value is False

    hass.states.async_set(
        entity_id, STATE_HOME, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert acc.char_detected.value is True

    hass.states.async_set(
        entity_id, STATE_NOT_HOME, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert acc.char_detected.value is False

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_detected.value is False


async def test_binary_device_classes(hass, hk_driver):
    """Test if services and characteristics are assigned correctly."""
    entity_id = "binary_sensor.demo"

    for device_class, (service, char, _) in BINARY_SENSOR_SERVICE_MAP.items():
        hass.states.async_set(entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: device_class})
        await hass.async_block_till_done()

        acc = BinarySensor(hass, hk_driver, "Binary Sensor", entity_id, 2, None)
        assert acc.get_service(service).display_name == service
        assert acc.char_detected.display_name == char


async def test_sensor_restore(hass, hk_driver, events):
    """Test setting up an entity from state in the event registry."""
    hass.state = CoreState.not_running

    registry = er.async_get(hass)

    registry.async_get_or_create(
        "sensor",
        "generic",
        "1234",
        suggested_object_id="temperature",
        original_device_class="temperature",
    )
    registry.async_get_or_create(
        "sensor",
        "generic",
        "12345",
        suggested_object_id="humidity",
        original_device_class="humidity",
        unit_of_measurement=PERCENTAGE,
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    acc = get_accessory(hass, hk_driver, hass.states.get("sensor.temperature"), 2, {})
    assert acc.category == 10

    acc = get_accessory(hass, hk_driver, hass.states.get("sensor.humidity"), 2, {})
    assert acc.category == 10


async def test_bad_name(hass, hk_driver):
    """Test an entity with a bad name."""
    entity_id = "sensor.humidity"

    hass.states.async_set(entity_id, "20")
    await hass.async_block_till_done()
    acc = HumiditySensor(hass, hk_driver, "[[Humid]]", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_humidity.value == 20
    assert acc.display_name == "--Humid--"


async def test_empty_name(hass, hk_driver):
    """Test an entity with a empty name."""
    entity_id = "sensor.humidity"

    hass.states.async_set(entity_id, "20")
    await hass.async_block_till_done()
    acc = HumiditySensor(hass, hk_driver, None, entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_humidity.value == 20
    assert acc.display_name == "None"
