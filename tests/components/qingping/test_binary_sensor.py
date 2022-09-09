"""Test the Qingping binary sensors."""

from unittest.mock import patch

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.qingping.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME

from . import LIGHT_AND_SIGNAL_SERVICE_INFO

from tests.common import MockConfigEntry


async def test_binary_sensors(hass):
    """Test setting up creates the binary sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all("binary_sensor")) == 0
    saved_callback(LIGHT_AND_SIGNAL_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("binary_sensor")) == 1

    motion_sensor = hass.states.get("binary_sensor.motion_light_eeff_motion")
    assert motion_sensor.state == "off"
    assert motion_sensor.attributes[ATTR_FRIENDLY_NAME] == "Motion & Light EEFF Motion"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
