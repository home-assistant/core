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
from homeassistant.helpers import device_registry
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


async def _async_setup_xiaomi_motion_device(hass):
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="DE:70:E8:B2:39:0C",
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_event_motion_detected(hass):
    """Make sure that a motion detected event is fired."""
    entry = await _async_setup_xiaomi_motion_device(hass)
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
    entry = await _async_setup_xiaomi_motion_device(hass)
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

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers_for_invalid_device_id(hass):
    """Test that we don't get triggers when using an invalid device_id."""
    entry = await _async_setup_xiaomi_motion_device(hass)

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement("DE:70:E8:B2:39:0C", b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()

    dev_reg = async_get_dev_reg(hass)

    invalid_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert invalid_device
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, invalid_device.id
    )
    assert triggers == []

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_if_fires_on_motion_detected(hass, calls):
    """Test for motion event trigger firing."""
    entry = await _async_setup_xiaomi_motion_device(hass)

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement("DE:70:E8:B2:39:0C", b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device({get_device_id("DE:70:E8:B2:39:0C")})
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

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_validate_trigger_invalid_trigger(hass, caplog):
    """Test for motion event with invalid triggers."""
    entry = await _async_setup_xiaomi_motion_device(hass)

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement("DE:70:E8:B2:39:0C", b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device({get_device_id("DE:70:E8:B2:39:0C")})
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
                        CONF_TYPE: "invalid",
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

    assert "motion_detected" in caplog.text

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
