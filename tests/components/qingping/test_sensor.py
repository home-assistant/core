"""Test the Qingping sensors."""
from homeassistant.components.qingping.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import LIGHT_AND_SIGNAL_SERVICE_INFO

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
    inject_bluetooth_service_info(hass, LIGHT_AND_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 1

    lux_sensor = hass.states.get("sensor.motion_light_eeff_illuminance")
    lux_sensor_attrs = lux_sensor.attributes
    assert lux_sensor.state == "13"
    assert lux_sensor_attrs[ATTR_FRIENDLY_NAME] == "Motion & Light EEFF Illuminance"
    assert lux_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert lux_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
