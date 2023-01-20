"""Test Xiaomi BLE events."""

from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.core import callback
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg

from . import make_advertisement

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_get_device_automations,
)
from tests.components.bluetooth import inject_bluetooth_service_info_bleak


@callback
def get_device_id(mac: str) -> tuple[str, str]:
    """Get device registry identifier for xiaomi_ble."""
    return (DOMAIN, f"{mac}")


async def test_event_motion_detected(hass):
    """Make sure that a motion detected event is fired."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="DE:70:E8:B2:39:0C",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit motion detected event
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement("DE:70:E8:B2:39:0C", b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["address"] == "DE:70:E8:B2:39:0C"
    assert events[0].data["event_type"] == "motion_detected"
    assert events[0].data["event_properties"] is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers(hass):
    """Test that we get the expected triggers from a Xiaomi BLE motion sensor."""
    mac = "DE:70:E8:B2:39:0C"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device({get_device_id("DE:70:E8:B2:39:0C")})
    assert device
    expected_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "device_id": device.id,
        "type": "motion_detected",
        "event_properties": None,
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers
