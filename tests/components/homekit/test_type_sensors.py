"""Test different accessory types: Sensors."""
from homeassistant.components.homekit.const import PROP_CELSIUS
from homeassistant.components.homekit.type_sensors import (
    AirQualitySensor, BinarySensor, CarbonDioxideSensor, HumiditySensor,
    LightSensor, TemperatureSensor, BINARY_SENSOR_SERVICE_MAP)
from homeassistant.const import (
    ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, STATE_HOME, STATE_NOT_HOME,
    STATE_OFF, STATE_ON, STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT)


async def test_temperature(hass):
    """Test if accessory is updated after state change."""
    entity_id = 'sensor.temperature'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = TemperatureSensor(hass, 'Temperature', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_temp.value == 0.0
    for key, value in PROP_CELSIUS.items():
        assert acc.char_temp.properties[key] == value

    hass.states.async_set(entity_id, STATE_UNKNOWN,
                          {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_temp.value == 0.0

    hass.states.async_set(entity_id, '20',
                          {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
    await hass.async_block_till_done()
    assert acc.char_temp.value == 20

    hass.states.async_set(entity_id, '75.2',
                          {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT})
    await hass.async_block_till_done()
    assert acc.char_temp.value == 24


async def test_humidity(hass):
    """Test if accessory is updated after state change."""
    entity_id = 'sensor.humidity'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = HumiditySensor(hass, 'Humidity', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_humidity.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_humidity.value == 0

    hass.states.async_set(entity_id, '20')
    await hass.async_block_till_done()
    assert acc.char_humidity.value == 20


async def test_air_quality(hass):
    """Test if accessory is updated after state change."""
    entity_id = 'sensor.air_quality'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = AirQualitySensor(hass, 'Air Quality', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_density.value == 0
    assert acc.char_quality.value == 0

    hass.states.async_set(entity_id, '34')
    await hass.async_block_till_done()
    assert acc.char_density.value == 34
    assert acc.char_quality.value == 1

    hass.states.async_set(entity_id, '200')
    await hass.async_block_till_done()
    assert acc.char_density.value == 200
    assert acc.char_quality.value == 5


async def test_co2(hass):
    """Test if accessory is updated after state change."""
    entity_id = 'sensor.co2'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = CarbonDioxideSensor(hass, 'CO2', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_co2.value == 0
    assert acc.char_peak.value == 0
    assert acc.char_detected.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_co2.value == 0
    assert acc.char_peak.value == 0
    assert acc.char_detected.value == 0

    hass.states.async_set(entity_id, '1100')
    await hass.async_block_till_done()
    assert acc.char_co2.value == 1100
    assert acc.char_peak.value == 1100
    assert acc.char_detected.value == 1

    hass.states.async_set(entity_id, '800')
    await hass.async_block_till_done()
    assert acc.char_co2.value == 800
    assert acc.char_peak.value == 1100
    assert acc.char_detected.value == 0


async def test_light(hass):
    """Test if accessory is updated after state change."""
    entity_id = 'sensor.light'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = LightSensor(hass, 'Light', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_light.value == 0.0001

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_light.value == 0.0001

    hass.states.async_set(entity_id, '300')
    await hass.async_block_till_done()
    assert acc.char_light.value == 300


async def test_binary(hass):
    """Test if accessory is updated after state change."""
    entity_id = 'binary_sensor.opening'

    hass.states.async_set(entity_id, STATE_UNKNOWN,
                          {ATTR_DEVICE_CLASS: 'opening'})
    await hass.async_block_till_done()

    acc = BinarySensor(hass, 'Window Opening', entity_id, 2, None)
    await hass.async_add_job(acc.run)

    assert acc.aid == 2
    assert acc.category == 10  # Sensor

    assert acc.char_detected.value == 0

    hass.states.async_set(entity_id, STATE_ON,
                          {ATTR_DEVICE_CLASS: 'opening'})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 1

    hass.states.async_set(entity_id, STATE_OFF,
                          {ATTR_DEVICE_CLASS: 'opening'})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0

    hass.states.async_set(entity_id, STATE_HOME,
                          {ATTR_DEVICE_CLASS: 'opening'})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 1

    hass.states.async_set(entity_id, STATE_NOT_HOME,
                          {ATTR_DEVICE_CLASS: 'opening'})
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_detected.value == 0


async def test_binary_device_classes(hass):
    """Test if services and characteristics are assigned correctly."""
    entity_id = 'binary_sensor.demo'

    for device_class, (service, char) in BINARY_SENSOR_SERVICE_MAP.items():
        hass.states.async_set(entity_id, STATE_OFF,
                              {ATTR_DEVICE_CLASS: device_class})
        await hass.async_block_till_done()

        acc = BinarySensor(hass, 'Binary Sensor', entity_id, 2, None)
        assert acc.get_service(service).display_name == service
        assert acc.char_detected.display_name == char
