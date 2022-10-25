"""Test the Oralb binary sensors."""


from homeassistant.components.oralb.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_ON

from . import ORALB_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_binary_sensors(hass):
    """Test setting up creates the binary sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ORALB_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("binary_sensor")) == 0
    inject_bluetooth_service_info(hass, ORALB_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("binary_sensor")) == 1

    motion_sensor = hass.states.get("binary_sensor.smart_series_7000_48be_brushing")
    assert motion_sensor.state == STATE_ON
    assert (
        motion_sensor.attributes[ATTR_FRIENDLY_NAME]
        == "Smart Series 7000 48BE Brushing"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
