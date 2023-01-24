"""Test the Mopeka sensors."""


from homeassistant.components.mopeka.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfLength,
    UnitOfTemperature,
)

from . import PRO_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors(hass):
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, PRO_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 3

    temp_sensor = hass.states.get("sensor.pro_eeff_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "30"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "Pro+ EEFF Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    tank_sensor = hass.states.get("sensor.pro_eeff_tank_level")
    tank_sensor_attrs = tank_sensor.attributes
    assert tank_sensor.state == "0"
    assert tank_sensor_attrs[ATTR_FRIENDLY_NAME] == "Pro+ EEFF Tank Level"
    assert tank_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert tank_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
