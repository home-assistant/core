"""The test for sensor device automation."""
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_DATE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TIMESTAMP,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


async def test_deprecated_temperature_conversion(
    hass, caplog, enable_custom_integrations
):
    """Test warning on deprecated temperature conversion."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test", native_value="0.0", native_unit_of_measurement=TEMP_FAHRENHEIT
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == "-17.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert (
        "Entity sensor.test (<class 'custom_components.test.sensor.MockSensor'>) "
        "with device_class None reports a temperature in °F which will be converted to "
        "°C. Temperature conversion for entities without correct device_class is "
        "deprecated and will be removed from Home Assistant Core 2022.3. Please update "
        "your configuration if device_class is manually configured, otherwise report it "
        "to the custom component author."
    ) in caplog.text


async def test_deprecated_last_reset(hass, caplog, enable_custom_integrations):
    """Test warning on deprecated last reset."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test", state_class="measurement", last_reset=dt_util.utc_from_timestamp(0)
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        "Entity sensor.test (<class 'custom_components.test.sensor.MockSensor'>) "
        "with state_class measurement has set last_reset. Setting last_reset for "
        "entities with state_class other than 'total' is deprecated and will be "
        "removed from Home Assistant Core 2021.11. Please update your configuration if "
        "state_class is manually configured, otherwise report it to the custom "
        "component author."
    ) in caplog.text


async def test_deprecated_unit_of_measurement(hass, caplog, enable_custom_integrations):
    """Test warning on deprecated unit_of_measurement."""
    SensorEntityDescription("catsensor", unit_of_measurement="cats")
    assert (
        "tests.components.sensor.test_init is setting 'unit_of_measurement' on an "
        "instance of SensorEntityDescription"
    ) in caplog.text


async def test_iso8601_values(hass, caplog, enable_custom_integrations):
    """Test values for iso8601."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="test1", device_class=DEVICE_CLASS_TIMESTAMP, native_value="invalid"
    )
    platform.ENTITIES["1"] = platform.MockSensor(
        name="test2", device_class=DEVICE_CLASS_DATE, native_value="invalid"
    )
    platform.ENTITIES["2"] = platform.MockSensor(
        name="test3",
        device_class=DEVICE_CLASS_TIMESTAMP,
        native_value="1970-01-01T00:00:00Z",
    )
    platform.ENTITIES["3"] = platform.MockSensor(
        name="test4", device_class=DEVICE_CLASS_DATE, native_value="1970-01-01"
    )
    platform.ENTITIES["4"] = platform.MockSensor(
        name="test5", device_class=DEVICE_CLASS_POWER, native_value=22
    )
    platform.ENTITIES["5"] = platform.MockSensor(
        name="test6", device_class=DEVICE_CLASS_TIMESTAMP, native_value=None
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        "Entity sensor.test1 (<class 'custom_components.test.sensor.MockSensor'>) with device_class (timestamp) reports an invalid value: invalid"
    ) in caplog.text
    assert (
        "Entity sensor.test2 (<class 'custom_components.test.sensor.MockSensor'>) with device_class (date) reports an invalid value: invalid"
    ) in caplog.text
    assert (
        "Entity sensor.test3 (<class 'custom_components.test.sensor.MockSensor'>) with device_class (timestamp) reports an invalid value: invalid"
    ) not in caplog.text
    assert (
        "Entity sensor.test4 (<class 'custom_components.test.sensor.MockSensor'>) with device_class (date) reports an invalid value: invalid"
    ) not in caplog.text
    assert (
        "Entity sensor.test5 (<class 'custom_components.test.sensor.MockSensor'>) with device_class (power) reports an invalid value: invalid"
    ) not in caplog.text
    assert (
        "Entity sensor.test6 (<class 'custom_components.test.sensor.MockSensor'>) with device_class (timestamp) reports an invalid value: invalid"
    ) not in caplog.text
