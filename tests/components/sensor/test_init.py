"""The test for sensor device automation."""
import pytest
from pytest import approx

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM


@pytest.mark.parametrize(
    "unit_system,native_unit,state_unit,native_value,state_value",
    [
        (IMPERIAL_SYSTEM, TEMP_FAHRENHEIT, TEMP_FAHRENHEIT, 100, 100),
        (IMPERIAL_SYSTEM, TEMP_CELSIUS, TEMP_FAHRENHEIT, 38, 100),
        (METRIC_SYSTEM, TEMP_FAHRENHEIT, TEMP_CELSIUS, 100, 38),
        (METRIC_SYSTEM, TEMP_CELSIUS, TEMP_CELSIUS, 38, 38),
    ],
)
async def test_temperature_conversion(
    hass,
    enable_custom_integrations,
    unit_system,
    native_unit,
    state_unit,
    native_value,
    state_value,
):
    """Test temperature conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=str(native_value),
        native_unit_of_measurement=native_unit,
        device_class=DEVICE_CLASS_TEMPERATURE,
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == approx(float(state_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == state_unit


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
