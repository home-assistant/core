"""Tests for LCN device triggers."""
from unittest.mock import patch

from homeassistant.components import automation
from homeassistant.components.lcn.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import MockPchkConnectionManager, get_device, init_integration

from tests.common import assert_lists_same, async_get_device_automations


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_get_triggers_module_device(hass, entry):
    """Test we get the expected triggers from a LCN module device."""
    await init_integration(hass, entry)
    device = get_device(hass, entry, (0, 7, False))

    expected_triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "transmitter",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "transponder",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "fingerprint",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "sendkeys",
        },
    ]

    triggers = await async_get_device_automations(hass, "trigger", device.id)

    assert_lists_same(triggers, expected_triggers)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_get_triggers_non_module_device(hass, entry):
    """Test we get the expected triggers from a LCN non-module device."""
    not_included_types = ("transmitter", "transponder", "fingerprint", "sendkeys")

    await init_integration(hass, entry)
    device_registry = dr.async_get(hass)
    for device_id in device_registry.devices:
        device = device_registry.async_get(device_id)
        if device.model.startswith(("LCN host", "LCN group", "LCN resource")):
            triggers = await async_get_device_automations(hass, "trigger", device_id)
            for trigger in triggers:
                assert trigger[CONF_TYPE] not in not_included_types


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_transponder_event_triggers_module_device(hass, calls, entry):
    """Test we get the expected triggers from a LCN non-module device."""
    await init_integration(hass, entry)
    device = get_device(hass, entry, (0, 7, False))

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: "transponder",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "test": "test_trigger_transponder",
                            "code": "{{ trigger.event.data.code }}",
                        },
                    },
                },
            ]
        },
    )

    event_data = {CONF_DEVICE_ID: device.id, "code": "aabbcc"}
    hass.bus.async_fire("lcn_transponder", event_data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["test"] == "test_trigger_transponder"
    assert calls[0].data["code"] == "aabbcc"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_fingerprint_event_triggers_module_device(hass, calls, entry):
    """Test we get the expected triggers from a LCN non-module device."""
    await init_integration(hass, entry)
    device = get_device(hass, entry, (0, 7, False))

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: "fingerprint",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "test": "test_trigger_fingerprint",
                            "code": "{{ trigger.event.data.code }}",
                        },
                    },
                },
            ]
        },
    )

    event_data = {CONF_DEVICE_ID: device.id, "code": "aabbcc"}
    hass.bus.async_fire("lcn_fingerprint", event_data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["test"] == "test_trigger_fingerprint"
    assert calls[0].data["code"] == "aabbcc"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_transmitter_event_triggers_module_device(hass, calls, entry):
    """Test we get the expected triggers from a LCN non-module device."""
    await init_integration(hass, entry)
    device = get_device(hass, entry, (0, 7, False))

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: "transmitter",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "test": "test_trigger_transmitter",
                            "code": "{{ trigger.event.data.code }}",
                            "level": "{{ trigger.event.data.level }}",
                            "key": "{{ trigger.event.data.key }}",
                            "action": "{{ trigger.event.data.action }}",
                        },
                    },
                },
            ]
        },
    )

    event_data = {
        CONF_DEVICE_ID: device.id,
        "code": "aabbcc",
        "level": 0,
        "key": 0,
        "action": "hit",
    }

    hass.bus.async_fire("lcn_transmitter", event_data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["test"] == "test_trigger_transmitter"
    assert calls[0].data["code"] == "aabbcc"
    assert calls[0].data["level"] == 0
    assert calls[0].data["key"] == 0
    assert calls[0].data["action"] == "hit"


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_sendkeys_event_triggers_module_device(hass, calls, entry):
    """Test we get the expected triggers from a LCN non-module device."""
    await init_integration(hass, entry)
    device = get_device(hass, entry, (0, 7, False))

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: "sendkeys",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "test": "test_trigger_sendkeys",
                            "key": "{{ trigger.event.data.key }}",
                            "action": "{{ trigger.event.data.action }}",
                        },
                    },
                },
            ]
        },
    )

    event_data = {
        CONF_DEVICE_ID: device.id,
        "key": "a1",
        "action": "hit",
    }

    hass.bus.async_fire("lcn_sendkeys", event_data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["test"] == "test_trigger_sendkeys"
    assert calls[0].data["key"] == "a1"
    assert calls[0].data["action"] == "hit"
