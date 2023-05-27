"""Test the BeeWi SmartClim sensors."""
from homeassistant.components.beewi_smartclim.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import SMART_CLIM_VALID

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, SMART_CLIM_VALID)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 3

    batt_sensor = hass.states.get("sensor.089352809434933736_battery")
    batt_sensor_attrs = batt_sensor.attributes
    assert batt_sensor.state == "44"
    assert batt_sensor_attrs[ATTR_FRIENDLY_NAME] == "089352809434933736 Battery"
    assert batt_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    humid_sensor = hass.states.get("sensor.089352809434933736_humidity")
    humid_sensor_attrs = humid_sensor.attributes
    assert humid_sensor.state == "86"
    assert humid_sensor_attrs[ATTR_FRIENDLY_NAME] == "089352809434933736 Humidity"
    assert humid_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humid_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.089352809434933736_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "14.7"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "089352809434933736 Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
