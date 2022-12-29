"""The tests for YoLink device triggers."""
import pytest

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.yolink import DOMAIN
from homeassistant.components.yolink.const import ATTR_DEVICE_SMART_REMOTE
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
)


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "yolink", "automation")


async def test_get_triggers(hass, device_reg):
    """Test we get the expected triggers from a yolink."""
    config_entry = MockConfigEntry(domain="yolink", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model=ATTR_DEVICE_SMART_REMOTE,
    )

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "remote_button_short_press",
            "device_id": device_entry.id,
            "subtype": "button_1",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "remote_button_long_press",
            "device_id": device_entry.id,
            "subtype": "button_1",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "remote_button_short_press",
            "device_id": device_entry.id,
            "subtype": "button_2",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "remote_button_long_press",
            "device_id": device_entry.id,
            "subtype": "button_2",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "remote_button_short_press",
            "device_id": device_entry.id,
            "subtype": "button_3",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "remote_button_long_press",
            "device_id": device_entry.id,
            "subtype": "button_3",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "remote_button_short_press",
            "device_id": device_entry.id,
            "subtype": "button_4",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "remote_button_long_press",
            "device_id": device_entry.id,
            "subtype": "button_4",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, expected_triggers)


async def test_if_fires_on_event(hass, calls, device_reg):
    """Test for event triggers firing."""
    mac_address = "12:34:56:AB:CD:EF"
    connection = (device_registry.CONNECTION_NETWORK_MAC, mac_address)
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={connection},
        identifiers={(DOMAIN, mac_address)},
        model=ATTR_DEVICE_SMART_REMOTE,
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "remote_button_short_press",
                        "subtype": "button_4",
                    },
                    "action": {
                        "service": "yolink.automation",
                        "data": {"message": "service called"},
                    },
                },
            ]
        },
    )

    device = device_reg.async_get_device(set(), {connection})
    assert device is not None
    # Fake remote button short press.
    hass.bus.async_fire(
        event_type=DOMAIN + "_event",
        event_data={
            "type": "remote_button_short_press",
            "device_id": device.id,
            "subtype": "button_4",
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["message"] == "service called"
