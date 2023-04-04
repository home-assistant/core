"""Tests for LCN device triggers."""
from pypck.inputs import ModSendKeysHost, ModStatusAccessControl
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import AccessControlPeriphery, KeyAction, SendKeyCommand
import voluptuous_serialize

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.lcn import device_trigger
from homeassistant.components.lcn.const import DOMAIN, KEY_ACTIONS, SENDKEYS
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import get_device

from tests.common import assert_lists_same, async_get_device_automations


async def test_get_triggers_module_device(
    hass: HomeAssistant, entry, lcn_connection
) -> None:
    """Test we get the expected triggers from a LCN module device."""
    device = get_device(hass, entry, (0, 7, False))

    expected_triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger,
            CONF_DEVICE_ID: device.id,
            "metadata": {},
        }
        for trigger in [
            "transmitter",
            "transponder",
            "fingerprint",
            "codelock",
            "send_keys",
        ]
    ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_non_module_device(
    hass: HomeAssistant, entry, lcn_connection
) -> None:
    """Test we get the expected triggers from a LCN non-module device."""
    not_included_types = ("transmitter", "transponder", "fingerprint", "send_keys")

    device_registry = dr.async_get(hass)
    host_device = device_registry.async_get_device({(DOMAIN, entry.entry_id)})
    group_device = get_device(hass, entry, (0, 5, True))
    resource_device = device_registry.async_get_device(
        {(DOMAIN, f"{entry.entry_id}-m000007-output1")}
    )

    for device in (host_device, group_device, resource_device):
        triggers = await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, device.id
        )
        for trigger in triggers:
            assert trigger[CONF_TYPE] not in not_included_types


async def test_if_fires_on_transponder_event(
    hass: HomeAssistant, calls, entry, lcn_connection
) -> None:
    """Test for transponder event triggers firing."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

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

    inp = ModStatusAccessControl(
        LcnAddr(*address),
        periphery=AccessControlPeriphery.TRANSPONDER,
        code="aabbcc",
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        "test": "test_trigger_transponder",
        "code": "aabbcc",
    }


async def test_if_fires_on_fingerprint_event(
    hass: HomeAssistant, calls, entry, lcn_connection
) -> None:
    """Test for fingerprint event triggers firing."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

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

    inp = ModStatusAccessControl(
        LcnAddr(*address),
        periphery=AccessControlPeriphery.FINGERPRINT,
        code="aabbcc",
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        "test": "test_trigger_fingerprint",
        "code": "aabbcc",
    }


async def test_if_fires_on_codelock_event(
    hass: HomeAssistant, calls, entry, lcn_connection
) -> None:
    """Test for codelock event triggers firing."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

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
                        CONF_TYPE: "codelock",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "test": "test_trigger_codelock",
                            "code": "{{ trigger.event.data.code }}",
                        },
                    },
                },
            ]
        },
    )

    inp = ModStatusAccessControl(
        LcnAddr(*address),
        periphery=AccessControlPeriphery.CODELOCK,
        code="aabbcc",
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        "test": "test_trigger_codelock",
        "code": "aabbcc",
    }


async def test_if_fires_on_transmitter_event(
    hass: HomeAssistant, calls, entry, lcn_connection
) -> None:
    """Test for transmitter event triggers firing."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

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

    inp = ModStatusAccessControl(
        LcnAddr(*address),
        periphery=AccessControlPeriphery.TRANSMITTER,
        code="aabbcc",
        level=0,
        key=0,
        action=KeyAction.HIT,
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        "test": "test_trigger_transmitter",
        "code": "aabbcc",
        "level": 0,
        "key": 0,
        "action": "hit",
    }


async def test_if_fires_on_send_keys_event(
    hass: HomeAssistant, calls, entry, lcn_connection
) -> None:
    """Test for send_keys event triggers firing."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

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
                        CONF_TYPE: "send_keys",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "test": "test_trigger_send_keys",
                            "key": "{{ trigger.event.data.key }}",
                            "action": "{{ trigger.event.data.action }}",
                        },
                    },
                },
            ]
        },
    )

    inp = ModSendKeysHost(
        LcnAddr(*address),
        actions=[SendKeyCommand.HIT, SendKeyCommand.DONTSEND, SendKeyCommand.DONTSEND],
        keys=[True, False, False, False, False, False, False, False],
    )

    await lcn_connection.async_process_input(inp)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        "test": "test_trigger_send_keys",
        "key": "a1",
        "action": "hit",
    }


async def test_get_transponder_trigger_capabilities(
    hass: HomeAssistant, entry, lcn_connection
) -> None:
    """Test we get the expected capabilities from a transponder device trigger."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "transponder",
            CONF_DEVICE_ID: device.id,
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"name": "code", "optional": True, "type": "string", "lower": True}]


async def test_get_fingerprint_trigger_capabilities(
    hass: HomeAssistant, entry, lcn_connection
) -> None:
    """Test we get the expected capabilities from a fingerprint device trigger."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "fingerprint",
            CONF_DEVICE_ID: device.id,
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [{"name": "code", "optional": True, "type": "string", "lower": True}]


async def test_get_transmitter_trigger_capabilities(
    hass: HomeAssistant, entry, lcn_connection
) -> None:
    """Test we get the expected capabilities from a transmitter device trigger."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "transmitter",
            CONF_DEVICE_ID: device.id,
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {"name": "code", "type": "string", "optional": True, "lower": True},
        {"name": "level", "type": "integer", "optional": True, "valueMin": 0},
        {"name": "key", "type": "integer", "optional": True, "valueMin": 0},
        {
            "name": "action",
            "type": "select",
            "optional": True,
            "options": [("hit", "hit"), ("make", "make"), ("break", "break")],
        },
    ]


async def test_get_send_keys_trigger_capabilities(
    hass: HomeAssistant, entry, lcn_connection
) -> None:
    """Test we get the expected capabilities from a send_keys device trigger."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "send_keys",
            CONF_DEVICE_ID: device.id,
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "key",
            "type": "select",
            "optional": True,
            "options": [(send_key.lower(), send_key.lower()) for send_key in SENDKEYS],
        },
        {
            "name": "action",
            "type": "select",
            "options": [
                (key_action.lower(), key_action.lower()) for key_action in KEY_ACTIONS
            ],
            "optional": True,
        },
    ]


async def test_unknown_trigger_capabilities(
    hass: HomeAssistant, entry, lcn_connection
) -> None:
    """Test we get empty capabilities if trigger is unknown."""
    address = (0, 7, False)
    device = get_device(hass, entry, address)

    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "dummy",
            CONF_DEVICE_ID: device.id,
        },
    )
    assert capabilities == {}
