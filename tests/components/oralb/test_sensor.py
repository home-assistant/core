"""Test the OralB sensors."""


from homeassistant.components.oralb.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME

from . import ORALB_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors(hass):
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ORALB_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, ORALB_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 7

    lux_sensor = hass.states.get("sensor.smart_series_7000_48be_toothbrush_state")
    lux_sensor_attrs = lux_sensor.attributes
    assert lux_sensor.state == "running"
    assert (
        lux_sensor_attrs[ATTR_FRIENDLY_NAME]
        == "Smart Series 7000 48BE Toothbrush State"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
