"""The tests for ONVIF device triggers."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.onvif import DOMAIN
from homeassistant.components.onvif.device import ONVIFDevice
from homeassistant.components.onvif.event import (
    CONF_ONVIF_EVENT,
    CONF_UNIQUE_ID,
    Event,
    EventManager,
)
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
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(hass, device_reg):
    """Test we get the expected triggers from a onvif."""
    # Add ONVIF config entry
    onvif_config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="12:34:56:AB:CD:EF", data={}
    )
    onvif_config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=onvif_config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    # Add another config entry for this device
    unifi_config_entry = MockConfigEntry(
        domain="unifi", unique_id="12:34:56:AB:CD:EF", data={}
    )
    unifi_config_entry.add_to_hass(hass)
    device_reg.async_get_or_create(
        config_entry_id=unifi_config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    # Create device and mock event
    device = ONVIFDevice(hass, onvif_config_entry)
    device.events = EventManager(hass, None, onvif_config_entry.unique_id)
    # pylint: disable=protected-access
    device.events._events = {
        f"{onvif_config_entry.unique_id}_tns1:RuleEngine/LineDetector/Crossed_0_0_0": Event(
            f"{onvif_config_entry.unique_id}_tns1:RuleEngine/LineDetector/Crossed_0_0_0",
            "0 Line Crossed",
            "event",
        )
    }
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][onvif_config_entry.unique_id] = device

    # Only expect triggers for ONVIF domain
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "event",
            "subtype": "0 Line Crossed",
            "device_id": device_entry.id,
            "unique_id": f"{onvif_config_entry.unique_id}_tns1:RuleEngine/LineDetector/Crossed_0_0_0",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_if_fires_on_event(hass, calls):
    """Test that onvif_event triggers firing."""
    event_uid = "12:34:56:AB:CD:EF_tns1:RuleEngine/LineDetector/Crossed_0_0_0"

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "type": "event",
                        "subtype": "0 Line Crossed",
                        "unique_id": event_uid,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform}} - "
                                "{{ trigger.event.event_type}} - {{ trigger.event.data.unique_id}}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Fire event
    hass.bus.fire(CONF_ONVIF_EVENT, {CONF_UNIQUE_ID: event_uid})
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == f"device - {CONF_ONVIF_EVENT} - {event_uid}"
