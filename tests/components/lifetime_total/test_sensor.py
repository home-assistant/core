"""Test the Lifetime Total integration."""

from homeassistant.components.lifetime_total.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_update_input_sensor(
    hass: HomeAssistant,
) -> None:
    """Test that sensor updates correctly when input sensor changes."""
    input_sensor_entity_id = "sensor.input"
    hass.states.async_set(
        input_sensor_entity_id,
        10,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
        },
    )
    lifetime_total_entity_id = "sensor.my_lifetime_total"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": input_sensor_entity_id,
            "name": "My lifetime_total",
        },
        title="My lifetime_total",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check initial value is set correctly
    state = hass.states.get(lifetime_total_entity_id)
    assert state.state == "10.0"
    assert state.attributes["last_reading"] == 10.0

    # Check input sensor increasing
    hass.states.async_set(
        "sensor.input",
        20,
    )
    await hass.async_block_till_done()
    state = hass.states.get(lifetime_total_entity_id)
    assert state.state == "20.0"
    assert state.attributes["last_reading"] == 20.0

    # Check input sensor decreasing
    hass.states.async_set(
        "sensor.input",
        5,
    )
    await hass.async_block_till_done()
    state = hass.states.get(lifetime_total_entity_id)
    assert state.state == "25.0"
    assert state.attributes["last_reading"] == 5.0

    # Check input sensor invalid value
    hass.states.async_set(
        "sensor.input",
        "abcde",
    )
    await hass.async_block_till_done()
    state = hass.states.get(lifetime_total_entity_id)
    assert state.state == "25.0"
    assert state.attributes["last_reading"] == 5.0
