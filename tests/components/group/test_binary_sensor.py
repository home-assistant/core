"""The tests for the Group Binary Sensor platform."""
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.group import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


async def test_default_state(hass):
    """Test binary_sensor group default state."""
    hass.states.async_set("binary_sensor.kitchen", "on")
    hass.states.async_set("binary_sensor.bedroom", "on")
    await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["binary_sensor.kitchen", "binary_sensor.bedroom"],
                "name": "Bedroom Group",
                "unique_id": "unique_identifier",
                "device_class": "presence",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.bedroom_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "binary_sensor.kitchen",
        "binary_sensor.bedroom",
    ]

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("binary_sensor.bedroom_group")
    assert entry
    assert entry.unique_id == "unique_identifier"
    assert entry.original_name == "Bedroom Group"
    assert entry.original_device_class == "presence"


async def test_state_reporting_all(hass):
    """Test the state reporting."""
    await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["binary_sensor.test1", "binary_sensor.test2"],
                "name": "Binary Sensor Group",
                "device_class": "presence",
                "all": "true",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    hass.states.async_set("binary_sensor.test1", STATE_OFF)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_ON

    hass.states.async_set("binary_sensor.test1", STATE_UNAVAILABLE)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNAVAILABLE
    )


async def test_state_reporting_any(hass):
    """Test the state reporting."""
    await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["binary_sensor.test1", "binary_sensor.test2"],
                "name": "Binary Sensor Group",
                "device_class": "presence",
                "all": "false",
                "unique_id": "unique_identifier",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # binary sensors have state off if unavailable
    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_ON

    hass.states.async_set("binary_sensor.test1", STATE_OFF)
    hass.states.async_set("binary_sensor.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_OFF

    hass.states.async_set("binary_sensor.test1", STATE_ON)
    hass.states.async_set("binary_sensor.test2", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.binary_sensor_group").state == STATE_ON

    # binary sensors have state off if unavailable
    hass.states.async_set("binary_sensor.test1", STATE_UNAVAILABLE)
    hass.states.async_set("binary_sensor.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.binary_sensor_group").state == STATE_UNAVAILABLE
    )

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("binary_sensor.binary_sensor_group")
    assert entry
    assert entry.unique_id == "unique_identifier"
