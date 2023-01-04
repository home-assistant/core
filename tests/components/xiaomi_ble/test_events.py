"""Test Xiaomi BLE events."""

from homeassistant.components.xiaomi_ble.const import DOMAIN

from . import make_advertisement

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info_bleak


async def test_xiaomi_motion_detected(hass):
    """Make sure that a motion detected event is fired."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="DE:70:E8:B2:39:0C",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement("DE:70:E8:B2:39:0C", b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
