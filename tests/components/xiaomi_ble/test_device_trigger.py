"""Test Xiaomi BLE events."""
import pytest

from homeassistant.components import automation
from homeassistant.components.bluetooth.const import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.xiaomi_ble.const import (
    CONF_EVENT_PROPERTIES,
    DOMAIN,
    EVENT_PROPERTIES,
    EVENT_TYPE,
    XIAOMI_BLE_EVENT,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.setup import async_setup_component

from . import make_advertisement

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_get_device_automations,
    async_mock_service,
)
from tests.components.bluetooth import inject_bluetooth_service_info_bleak


@callback
def get_device_id(mac: str) -> tuple[str, str]:
    """Get device registry identifier for xiaomi_ble."""
    return (BLUETOOTH_DOMAIN, mac)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


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

    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement("DE:70:E8:B2:39:0C", b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device({get_device_id("DE:70:E8:B2:39:0C")})
    assert device
    expected_trigger = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "motion_detected",
        CONF_EVENT_PROPERTIES: None,
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers


async def test_if_fires_on_motion_detected(hass, calls):
    """Test for motion event trigger firing."""
    mac = "DE:70:E8:B2:39:0C"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device({get_device_id(mac)})
    device_id = device.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "motion_detected",
                        CONF_EVENT_PROPERTIES: None,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_motion_detected"},
                    },
                },
            ]
        },
    )

    message = {
        CONF_DEVICE_ID: device_id,
        CONF_ADDRESS: "DE:70:E8:B2:39:0C",
        EVENT_TYPE: "motion_detected",
        EVENT_PROPERTIES: None,
    }

    hass.bus.async_fire(XIAOMI_BLE_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_motion_detected"
