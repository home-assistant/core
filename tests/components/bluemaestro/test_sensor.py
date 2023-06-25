"""Test the BlueMaestro sensors."""
from homeassistant.components.bluemaestro.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import BLUEMAESTRO_SERVICE_INFO

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
    inject_bluetooth_service_info(hass, BLUEMAESTRO_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 4

    humid_sensor = hass.states.get("sensor.tempo_disc_thd_eeff_temperature")
    humid_sensor_attrs = humid_sensor.attributes
    assert humid_sensor.state == "24.2"
    assert humid_sensor_attrs[ATTR_FRIENDLY_NAME] == "Tempo Disc THD EEFF Temperature"
    assert humid_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert humid_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
