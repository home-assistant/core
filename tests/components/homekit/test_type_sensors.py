"""Test different accessory types: Sensors."""

from unittest.mock import patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.homekit import get_accessory
from homeassistant.components.homekit.const import (
    CONF_THRESHOLD_CO,
    CONF_THRESHOLD_CO2,
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
    NitrogenDioxideSensor,
    PM10Sensor,
    PM25Sensor,
    TemperatureSensor,
    VolatileOrganicCompoundsSensor,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_temperature(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.temperature"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = TemperatureSensor(hass, hk_driver, "Temperature", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_temp.value == 0.0
    for key, value in PROP_CELSIUS.items():
        assert acc.char_temp.properties[key] == value

    hass.states.async_set(
        entity_id, STATE_UNKNOWN, {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    await hass.async_block_till_done()
    assert acc.char_temp.value == 0.0

    hass.states.async_set(
        entity_id, "20", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    await hass.async_block_till_done()
    assert acc.char_temp.value == 20

    hass.states.async_set(
        entity_id, "0", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    await hass.async_block_till_done()
    assert acc.char_temp.value == 0

    # The UOM changes, the accessory should reload itself
    with patch.object(acc, "async_reload") as mock_reload:
        hass.states.async_set(
            entity_id, "75.2", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT}
        )
        await hass.async_block_till_done()
        assert mock_reload.called


async def test_humidity(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.humidity"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = HumiditySensor(hass, hk_driver, "Humidity", entity_id, 2, None)
    acc.run()
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


async def test_air_quality(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.air_quality"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, hk_driver, "Air Quality", entity_id, 2, None)
    acc.run()
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


async def test_pm10(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.air_quality_pm10"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = PM10Sensor(hass, hk_driver, "PM10 Sensor", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, "54")
    await hass.async_block_till_done()
    assert acc.char_density.value == 54
    assert acc.char_quality.value == 1

    hass.states.async_set(entity_id, "154")
    await hass.async_block_till_done()
    assert acc.char_density.value == 154
    assert acc.char_quality.value == 2

    hass.states.async_set(entity_id, "254")
    await hass.async_block_till_done()
    assert acc.char_density.value == 254
    assert acc.char_quality.value == 3

    hass.states.async_set(entity_id, "354")
    await hass.async_block_till_done()
    assert acc.char_density.value == 354
    assert acc.char_quality.value == 4

    hass.states.async_set(entity_id, "400")
    await hass.async_block_till_done()
    assert acc.char_density.value == 400
    assert acc.char_quality.value == 5


async def test_pm25(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.air_quality_pm25"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = PM25Sensor(hass, hk_driver, "PM25 Sensor", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, "8")
    await hass.async_block_till_done()
    assert acc.char_density.value == 8
    assert acc.char_quality.value == 1

    hass.states.async_set(entity_id, "12")
    await hass.async_block_till_done()
    assert acc.char_density.value == 12
    assert acc.char_quality.value == 2

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


async def test_no2(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.air_quality_nitrogen_dioxide"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = NitrogenDioxideSensor(
        hass, hk_driver, "Nitrogen Dioxide Sensor", entity_id, 2, None
    )
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, "30")
    await hass.async_block_till_done()
    assert acc.char_density.value == 30
    assert acc.char_quality.value == 1

    hass.states.async_set(entity_id, "60")
    await hass.async_block_till_done()
    assert acc.char_density.value == 60
    assert acc.char_quality.value == 2

    hass.states.async_set(entity_id, "80")
    await hass.async_block_till_done()
    assert acc.char_density.value == 80
    assert acc.char_quality.value == 3

    hass.states.async_set(entity_id, "90")
    await hass.async_block_till_done()
    assert acc.char_density.value == 90
    assert acc.char_quality.value == 4

    hass.states.async_set(entity_id, "100")
    await hass.async_block_till_done()
    assert acc.char_density.value == 100
    assert acc.char_quality.value == 5


async def test_voc(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.air_quality_volatile_organic_compounds"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = VolatileOrganicCompoundsSensor(
        hass, hk_driver, "Volatile Organic Compounds Sensor", entity_id, 2, None
    )
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, "250")
    await hass.async_block_till_done()
    assert acc.char_density.value == 250
    assert acc.char_quality.value == 1

    hass.states.async_set(entity_id, "500")
    await hass.async_block_till_done()
    assert acc.char_density.value == 500
    assert acc.char_quality.value == 2

    hass.states.async_set(entity_id, "1000")
    await hass.async_block_till_done()
    assert acc.char_density.value == 1000
    assert acc.char_quality.value == 3

    hass.states.async_set(entity_id, "3000")
    await hass.async_block_till_done()
    assert acc.char_density.value == 3000
    assert acc.char_quality.value == 4

    hass.states.async_set(entity_id, "5000")
    await hass.async_block_till_done()
    assert acc.char_density.value == 5000
    assert acc.char_quality.value == 5


async def test_co(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.co"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = CarbonMonoxideSensor(hass, hk_driver, "CO", entity_id, 2, None)
    acc.run()
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


async def test_co_with_configured_threshold(hass: HomeAssistant, hk_driver) -> None:
    """Test if co threshold of accessory can be configured ."""
    entity_id = "sensor.co"

    co_threshold = 10
    assert co_threshold < THRESHOLD_CO

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = CarbonMonoxideSensor(
        hass, hk_driver, "CO", entity_id, 2, {CONF_THRESHOLD_CO: co_threshold}
    )
    acc.run()
    await hass.async_block_till_done()

    value = 15
    assert value > co_threshold
    hass.states.async_set(entity_id, str(value))
    await hass.async_block_till_done()
    assert acc.char_detected.value == 1

    value = 5
    assert value < co_threshold
    hass.states.async_set(entity_id, str(value))
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0


async def test_co2(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.co2"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = CarbonDioxideSensor(hass, hk_driver, "CO2", entity_id, 2, None)
    acc.run()
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


async def test_co2_with_configured_threshold(hass: HomeAssistant, hk_driver) -> None:
    """Test if co2 threshold of accessory can be configured ."""
    entity_id = "sensor.co2"

    co2_threshold = 500
    assert co2_threshold < THRESHOLD_CO2

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = CarbonDioxideSensor(
        hass, hk_driver, "CO2", entity_id, 2, {CONF_THRESHOLD_CO2: co2_threshold}
    )
    acc.run()
    await hass.async_block_till_done()

    value = 800
    assert value > co2_threshold
    hass.states.async_set(entity_id, str(value))
    await hass.async_block_till_done()
    assert acc.char_detected.value == 1

    value = 400
    assert value < co2_threshold
    hass.states.async_set(entity_id, str(value))
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0


async def test_light(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "sensor.light"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = LightSensor(hass, hk_driver, "Light", entity_id, 2, None)
    acc.run()
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


async def test_binary(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "binary_sensor.opening"

    hass.states.async_set(entity_id, STATE_UNKNOWN, {ATTR_DEVICE_CLASS: "opening"})
    await hass.async_block_till_done()

    acc = BinarySensor(hass, hk_driver, "Window Opening", entity_id, 2, None)
    acc.run()
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

    hass.states.async_set(entity_id, STATE_UNKNOWN, {ATTR_DEVICE_CLASS: "opening"})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0

    hass.states.async_set(entity_id, STATE_UNAVAILABLE, {ATTR_DEVICE_CLASS: "opening"})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0


async def test_motion_uses_bool(hass: HomeAssistant, hk_driver) -> None:
    """Test if accessory is updated after state change."""
    entity_id = "binary_sensor.motion"

    hass.states.async_set(
        entity_id, STATE_UNKNOWN, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()

    acc = BinarySensor(hass, hk_driver, "Motion Sensor", entity_id, 2, None)
    acc.run()
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
        entity_id, STATE_UNKNOWN, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert acc.char_detected.value is False

    hass.states.async_set(
        entity_id,
        STATE_UNAVAILABLE,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION},
    )
    await hass.async_block_till_done()
    assert acc.char_detected.value is False

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_detected.value is False


async def test_binary_device_classes(hass: HomeAssistant, hk_driver) -> None:
    """Test if services and characteristics are assigned correctly."""
    entity_id = "binary_sensor.demo"
    aid = 1

    for device_class, (service, char, _) in BINARY_SENSOR_SERVICE_MAP.items():
        hass.states.async_set(entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: device_class})
        await hass.async_block_till_done()

        aid += 1
        acc = BinarySensor(hass, hk_driver, "Binary Sensor", entity_id, aid, None)
        assert acc.get_service(service).display_name == service
        assert acc.char_detected.display_name == char


async def test_sensor_restore(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, hk_driver
) -> None:
    """Test setting up an entity from state in the event registry."""
    hass.set_state(CoreState.not_running)

    entity_registry.async_get_or_create(
        "sensor",
        "generic",
        "1234",
        suggested_object_id="temperature",
        original_device_class="temperature",
    )
    entity_registry.async_get_or_create(
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

    acc = get_accessory(hass, hk_driver, hass.states.get("sensor.humidity"), 3, {})
    assert acc.category == 10


async def test_bad_name(hass: HomeAssistant, hk_driver) -> None:
    """Test an entity with a bad name."""
    entity_id = "sensor.humidity"

    hass.states.async_set(entity_id, "20")
    await hass.async_block_till_done()
    acc = HumiditySensor(hass, hk_driver, "[[Humid]]", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_humidity.value == 20
    assert acc.display_name == "Humid"


async def test_empty_name(hass: HomeAssistant, hk_driver) -> None:
    """Test an entity with a empty name."""
    entity_id = "sensor.humidity"

    hass.states.async_set(entity_id, "20")
    await hass.async_block_till_done()
    acc = HumiditySensor(hass, hk_driver, None, entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_humidity.value == 20
    assert acc.display_name == "None"
