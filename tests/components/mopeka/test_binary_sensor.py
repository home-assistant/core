"""Test the Mopeka binary sensors."""


from homeassistant.components.mopeka.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME

from . import PRO_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_binary_sensors(hass):
    """Test setting up creates the binary sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("binary_sensor")) == 0
    inject_bluetooth_service_info(hass, PRO_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("binary_sensor")) == 1

    motion_sensor = hass.states.get("binary_sensor.pro_eeff_button_pushed")
    assert motion_sensor.state == "off"
    assert motion_sensor.attributes[ATTR_FRIENDLY_NAME] == "Pro+ EEFF Button pushed"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
