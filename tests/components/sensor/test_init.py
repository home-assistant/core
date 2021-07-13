"""The test for sensor device automation."""
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.setup import async_setup_component


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
        "with device_class None reports a temperature in °F which will be converted to °C, this is deprecated "
        "and will be removed from Home Assistant "
        "Core 2021.10. Please update your configuration if device_class is "
        "manually configured, otherwise report it to the custom component author."
    ) in caplog.text
