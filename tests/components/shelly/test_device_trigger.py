"""The tests for Shelly device triggers."""
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant import setup
from homeassistant.components import automation
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.shelly import ShellyDeviceWrapper
from homeassistant.components.shelly.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    COAP,
    CONF_SUBTYPE,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    EVENT_SHELLY_CLICK,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)


async def test_get_triggers(hass, coap_wrapper):
    """Test we get the expected triggers from a shelly."""
    assert coap_wrapper
    expected_triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: coap_wrapper.device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "single",
            CONF_SUBTYPE: "button1",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: coap_wrapper.device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "long",
            CONF_SUBTYPE: "button1",
        },
    ]

    triggers = await async_get_device_automations(
        hass, "trigger", coap_wrapper.device_id
    )

    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_button(hass):
    """Test we get the expected triggers from a shelly button."""
    await async_setup_component(hass, "shelly", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"sleep_period": 43200, "model": "SHBTN-1"},
        unique_id="12345678",
    )
    config_entry.add_to_hass(hass)

    device = Mock(
        blocks=None,
        settings=None,
        shelly=None,
        update=AsyncMock(),
        initialized=False,
    )

    hass.data[DOMAIN] = {DATA_CONFIG_ENTRY: {}}
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id] = {}
    coap_wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][
        COAP
    ] = ShellyDeviceWrapper(hass, config_entry, device)

    await coap_wrapper.async_setup()

    expected_triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: coap_wrapper.device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "single",
            CONF_SUBTYPE: "button",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: coap_wrapper.device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "double",
            CONF_SUBTYPE: "button",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: coap_wrapper.device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "triple",
            CONF_SUBTYPE: "button",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: coap_wrapper.device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "long",
            CONF_SUBTYPE: "button",
        },
    ]

    triggers = await async_get_device_automations(
        hass, "trigger", coap_wrapper.device_id
    )

    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_for_invalid_device_id(hass, device_reg, coap_wrapper):
    """Test error raised for invalid shelly device_id."""
    assert coap_wrapper
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    invalid_device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_get_device_automations(hass, "trigger", invalid_device.id)


async def test_if_fires_on_click_event(hass, calls, coap_wrapper):
    """Test for click_event trigger firing."""
    assert coap_wrapper
    await setup.async_setup_component(hass, "persistent_notification", {})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: coap_wrapper.device_id,
                        CONF_TYPE: "single",
                        CONF_SUBTYPE: "button1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_single_click"},
                    },
                },
            ]
        },
    )

    message = {
        CONF_DEVICE_ID: coap_wrapper.device_id,
        ATTR_CLICK_TYPE: "single",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_single_click"


async def test_validate_trigger_config_no_device(hass, calls, coap_wrapper):
    """Test for click_event with no device."""
    assert coap_wrapper
    await setup.async_setup_component(hass, "persistent_notification", {})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: "no_device",
                        CONF_TYPE: "single",
                        CONF_SUBTYPE: "button1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_single_click"},
                    },
                },
            ]
        },
    )
    message = {CONF_DEVICE_ID: "no_device", ATTR_CLICK_TYPE: "single", ATTR_CHANNEL: 1}
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_single_click"


async def test_validate_trigger_invalid_triggers(hass, coap_wrapper):
    """Test for click_event with invalid triggers."""
    assert coap_wrapper
    notification_calls = async_mock_service(hass, "persistent_notification", "create")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: coap_wrapper.device_id,
                        CONF_TYPE: "single",
                        CONF_SUBTYPE: "button3",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_single_click"},
                    },
                },
            ]
        },
    )

    assert len(notification_calls) == 1
    assert (
        "The following integrations and platforms could not be set up"
        in notification_calls[0].data["message"]
    )
