"""The test for the attribute sensor platform."""
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component


async def test_default_name_sensor(hass: HomeAssistant) -> None:
    """Test the min sensor with a default name."""
    config = {
        "sensor": {
            "platform": "attribute_sensor",
            "source": "sensor.sensor_one",
            "attribute": "attribute1",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.sensor_one", "home", {"attribute1": "75", "attribute2": "100"}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.attribute1_sensor")

    assert state.state == "75"


async def test_attribute_sensor(hass: HomeAssistant) -> None:
    """Test the attribute sensor."""
    config = {
        "sensor": {
            "platform": "attribute_sensor",
            "name": "test_attribute_sensor",
            "source": "sensor.sensor_one",
            "attribute": "attribute2",
            "device_class": SensorDeviceClass.HUMIDITY,
            "unique_id": "very_unique_id",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.sensor_one", "home", {"attribute1": 75, "attribute2": 100}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_attribute_sensor")

    assert state.state == "100"
    assert state.attributes["device_class"] == SensorDeviceClass.HUMIDITY

    entity_reg = er.async_get(hass)
    entity = entity_reg.async_get("sensor.test_attribute_sensor")
    assert entity.unique_id == "very_unique_id"
