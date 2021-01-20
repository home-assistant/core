"""The tests for Shelly device triggers."""
import pytest

from homeassistant import setup
from homeassistant.components import automation
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.lutron_caseta.const import (
    ATTR_CHANNEL,
    BUTTON_DEVICES,
    CONF_SUBTYPE,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
)
from homeassistant.components.lutron_caseta.device_trigger import CONF_SUBTYPE
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture
async def lutron_with_picos(hass):
    """Setups a lutron bridge with picos."""
    await async_setup_component(hass, DOMAIN, {})

    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    hass.data[DOMAIN][config_entry.entry_id] = {BUTTON_DEVICES: {}}

    yield hass.data[DOMAIN][config_entry.entry_id][BUTTON_DEVICES]


async def test_get_triggers(hass, lutron_with_picos):
    """Test we get the expected triggers from a shelly."""
    assert lutron_with_picos
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


async def test_get_triggers_for_invalid_device_id(hass, device_reg, lutron_with_picos):
    """Test error raised for invalid shelly device_id."""
    assert lutron_with_picos
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    invalid_device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_get_device_automations(hass, "trigger", invalid_device.id)


async def test_if_fires_on_click_event(hass, calls, lutron_with_picos):
    """Test for click_event trigger firing."""
    assert lutron_with_picos
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
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_single_click"


async def test_validate_trigger_config_no_device(hass, calls, lutron_with_picos):
    """Test for click_event with no device."""
    assert lutron_with_picos
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
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
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
