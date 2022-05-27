"""The tests for Shelly device triggers."""
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.shelly import BlockDeviceWrapper
from homeassistant.components.shelly.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    BLOCK,
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
)


@pytest.mark.parametrize(
    "button_type, is_valid",
    [
        ("momentary", True),
        ("momentary_on_release", True),
        ("detached", True),
        ("toggle", False),
    ],
)
async def test_get_triggers_block_device(
    hass, coap_wrapper, monkeypatch, button_type, is_valid
):
    """Test we get the expected triggers from a shelly block device."""
    assert coap_wrapper

    monkeypatch.setitem(
        coap_wrapper.device.settings,
        "relays",
        [
            {"btn_type": button_type},
            {"btn_type": "toggle"},
        ],
    )

    expected_triggers = []
    if is_valid:
        expected_triggers = [
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: coap_wrapper.device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: type,
                CONF_SUBTYPE: "button1",
                "metadata": {},
            }
            for type in ["single", "long"]
        ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, coap_wrapper.device_id
    )

    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_rpc_device(hass, rpc_wrapper):
    """Test we get the expected triggers from a shelly RPC device."""
    assert rpc_wrapper
    expected_triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: rpc_wrapper.device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: type,
            CONF_SUBTYPE: "button1",
            "metadata": {},
        }
        for type in ["btn_down", "btn_up", "single_push", "double_push", "long_push"]
    ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, rpc_wrapper.device_id
    )

    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_button(hass):
    """Test we get the expected triggers from a shelly button."""
    await async_setup_component(hass, "shelly", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"sleep_period": 43200, "model": "SHBTN-1", "host": "1.2.3.4"},
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
        BLOCK
    ] = BlockDeviceWrapper(hass, config_entry, device)

    coap_wrapper.async_setup()

    expected_triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: coap_wrapper.device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: type,
            CONF_SUBTYPE: "button",
            "metadata": {},
        }
        for type in ["single", "double", "triple", "long"]
    ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, coap_wrapper.device_id
    )

    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_non_initialized_devices(hass):
    """Test we get the empty triggers for non-initialized devices."""
    await async_setup_component(hass, "shelly", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"sleep_period": 43200, "model": "SHDW-2", "host": "1.2.3.4"},
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
        BLOCK
    ] = BlockDeviceWrapper(hass, config_entry, device)

    coap_wrapper.async_setup()

    expected_triggers = []

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, coap_wrapper.device_id
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
        await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, invalid_device.id
        )


async def test_if_fires_on_click_event_block_device(hass, calls, coap_wrapper):
    """Test for click_event trigger firing for block device."""
    assert coap_wrapper

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


async def test_if_fires_on_click_event_rpc_device(hass, calls, rpc_wrapper):
    """Test for click_event trigger firing for rpc device."""
    assert rpc_wrapper

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: rpc_wrapper.device_id,
                        CONF_TYPE: "single_push",
                        CONF_SUBTYPE: "button1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_single_push"},
                    },
                },
            ]
        },
    )

    message = {
        CONF_DEVICE_ID: rpc_wrapper.device_id,
        ATTR_CLICK_TYPE: "single_push",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_single_push"


async def test_validate_trigger_block_device_not_ready(hass, calls, coap_wrapper):
    """Test validate trigger config when block device is not ready."""
    assert coap_wrapper

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: "device_not_ready",
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
        CONF_DEVICE_ID: "device_not_ready",
        ATTR_CLICK_TYPE: "single",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_single_click"


async def test_validate_trigger_rpc_device_not_ready(hass, calls, rpc_wrapper):
    """Test validate trigger config when RPC device is not ready."""
    assert rpc_wrapper

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: "device_not_ready",
                        CONF_TYPE: "single_push",
                        CONF_SUBTYPE: "button1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_single_push"},
                    },
                },
            ]
        },
    )
    message = {
        CONF_DEVICE_ID: "device_not_ready",
        ATTR_CLICK_TYPE: "single_push",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_single_push"


async def test_validate_trigger_invalid_triggers(hass, coap_wrapper):
    """Test for click_event with invalid triggers."""
    assert coap_wrapper

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

    assert len(notifications := hass.states.async_all("persistent_notification")) == 1
    assert (
        "The following integrations and platforms could not be set up"
        in notifications[0].attributes["message"]
    )
