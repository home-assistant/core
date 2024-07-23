"""The tests for Lutron Caséta device triggers."""

from unittest.mock import patch

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.lutron_caseta import (
    ATTR_ACTION,
    ATTR_AREA_NAME,
    ATTR_DEVICE_NAME,
    ATTR_SERIAL,
    ATTR_TYPE,
)
from homeassistant.components.lutron_caseta.const import (
    ATTR_BUTTON_TYPE,
    ATTR_LEAP_BUTTON_NUMBER,
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
)
from homeassistant.components.lutron_caseta.device_trigger import CONF_SUBTYPE
from homeassistant.components.lutron_caseta.models import LutronCasetaData
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_HOST,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import MockBridge

from tests.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
)

MOCK_BUTTON_DEVICES = [
    {
        "device_id": "9",
        "Name": "Dining Room_Pico",
        "ID": 2,
        "Area": {"Name": "Back Hall"},
        "Buttons": [
            {"Number": 2},
            {"Number": 3},
            {"Number": 4},
            {"Number": 5},
            {"Number": 6},
        ],
        "leap_name": "Dining Room_Pico",
        "type": "Pico3ButtonRaiseLower",
        "model": "PJ2-3BRL-GXX-X01",
        "serial": 68551522,
    },
    {
        "device_id": "1355",
        "Name": "Main Stairs Position 1 Keypad",
        "ID": 3,
        "Area": {"Name": "Front Steps"},
        "Buttons": [
            {"Number": 7},
            {"Number": 8},
            {"Number": 9},
            {"Number": 10},
            {"Number": 11},
        ],
        "leap_name": "Front Steps_Front Steps Sunnata Keypad",
        "type": "SunnataKeypad",
        "model": "RRST-W4B-XX",
        "serial": 66286451,
    },
    {
        "device_id": "786",
        "Name": "Example Homeowner Keypad",
        "ID": 4,
        "Area": {"Name": "Front Steps"},
        "Buttons": [
            {"Number": 12},
            {"Number": 13},
            {"Number": 14},
            {"Number": 15},
            {"Number": 16},
            {"Number": 17},
            {"Number": 18},
        ],
        "leap_name": "Front Steps_Example Homeowner Keypad",
        "type": "HomeownerKeypad",
        "model": "Homeowner Keypad",
        "serial": "1234_786",
    },
]


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def _async_setup_lutron_with_picos(hass):
    """Setups a lutron bridge with picos."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_KEYFILE: "",
            CONF_CERTFILE: "",
            CONF_CA_CERTS: "",
        },
        unique_id="abc",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lutron_caseta.Smartbridge.create_tls",
        return_value=MockBridge(can_connect=True),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry.entry_id


async def test_get_triggers(hass: HomeAssistant) -> None:
    """Test we get the expected triggers from a lutron pico."""
    config_entry_id = await _async_setup_lutron_with_picos(hass)
    data: LutronCasetaData = hass.data[DOMAIN][config_entry_id]
    keypads = data.keypad_data.keypads
    device_id = keypads[list(keypads)[0]]["dr_device_id"]

    expected_triggers = [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: subtype,
            CONF_TYPE: "press",
            "metadata": {},
        }
        for subtype in ["on", "stop", "off", "raise", "lower"]
    ]
    expected_triggers += [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: subtype,
            CONF_TYPE: "release",
            "metadata": {},
        }
        for subtype in ["on", "stop", "off", "raise", "lower"]
    ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_id
    )

    assert triggers == unordered(expected_triggers)


async def test_get_triggers_for_invalid_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test error raised for invalid lutron device_id."""
    config_entry_id = await _async_setup_lutron_with_picos(hass)

    invalid_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, invalid_device.id
    )

    assert triggers == []


async def test_get_triggers_for_non_button_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test error raised for invalid lutron device_id."""
    config_entry_id = await _async_setup_lutron_with_picos(hass)

    invalid_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, "invdevserial")},
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, invalid_device.id
    )

    assert triggers == []


async def test_none_serial_keypad(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test serial assignment for keypads without serials."""
    config_entry_id = await _async_setup_lutron_with_picos(hass)

    keypad_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, "1234_786")},
    )

    assert keypad_device is not None


async def test_if_fires_on_button_event(
    hass: HomeAssistant, calls, device_registry: dr.DeviceRegistry
) -> None:
    """Test for press trigger firing."""
    await _async_setup_lutron_with_picos(hass)

    device = MOCK_BUTTON_DEVICES[0]
    dr_device = device_registry.async_get_device(
        identifiers={(DOMAIN, device["serial"])}
    )
    device_id = dr_device.id

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
                        CONF_TYPE: "press",
                        CONF_SUBTYPE: "on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )

    message = {
        ATTR_SERIAL: device.get("serial"),
        ATTR_TYPE: device.get("type"),
        ATTR_LEAP_BUTTON_NUMBER: 0,
        ATTR_DEVICE_NAME: device["Name"],
        ATTR_AREA_NAME: device.get("Area", {}).get("Name"),
        ATTR_ACTION: "press",
        ATTR_DEVICE_ID: device_id,
        ATTR_BUTTON_TYPE: "on",
    }
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_button_press"


async def test_if_fires_on_button_event_without_lip(
    hass: HomeAssistant, calls, device_registry: dr.DeviceRegistry
) -> None:
    """Test for press trigger firing on a device that does not support lip."""
    await _async_setup_lutron_with_picos(hass)
    device = MOCK_BUTTON_DEVICES[1]
    dr_device = device_registry.async_get_device(
        identifiers={(DOMAIN, device["serial"])}
    )
    device_id = dr_device.id
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
                        CONF_TYPE: "press",
                        CONF_SUBTYPE: "Kitchen Pendants",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )

    message = {
        ATTR_SERIAL: device.get("serial"),
        ATTR_TYPE: device.get("type"),
        ATTR_LEAP_BUTTON_NUMBER: 3,
        ATTR_DEVICE_NAME: device["Name"],
        ATTR_AREA_NAME: device.get("Area", {}).get("Name"),
        ATTR_ACTION: "press",
        ATTR_DEVICE_ID: device_id,
        ATTR_BUTTON_TYPE: "Kitchen Pendants",
    }
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_button_press"


async def test_validate_trigger_config_no_device(hass: HomeAssistant, calls) -> None:
    """Test for no press with no device."""

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
                        CONF_TYPE: "press",
                        CONF_SUBTYPE: "on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    message = {
        ATTR_SERIAL: "123",
        ATTR_TYPE: "any",
        ATTR_LEAP_BUTTON_NUMBER: 0,
        ATTR_DEVICE_NAME: "any",
        ATTR_AREA_NAME: "area",
        ATTR_ACTION: "press",
    }
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_validate_trigger_config_unknown_device(
    hass: HomeAssistant, calls
) -> None:
    """Test for no press with an unknown device."""

    config_entry_id = await _async_setup_lutron_with_picos(hass)
    data: LutronCasetaData = hass.data[DOMAIN][config_entry_id]
    keypads = data.keypad_data.keypads
    lutron_device_id = list(keypads)[0]
    keypad = keypads[lutron_device_id]
    device_id = keypad["dr_device_id"]
    keypad["type"] = "unknown"

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
                        CONF_TYPE: "press",
                        CONF_SUBTYPE: "on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    message = {
        ATTR_SERIAL: "123",
        ATTR_TYPE: "any",
        ATTR_LEAP_BUTTON_NUMBER: 0,
        ATTR_DEVICE_NAME: "any",
        ATTR_AREA_NAME: "area",
        ATTR_ACTION: "press",
    }
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_validate_trigger_invalid_triggers(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for click_event with invalid triggers."""
    config_entry_id = await _async_setup_lutron_with_picos(hass)
    data: LutronCasetaData = hass.data[DOMAIN][config_entry_id]
    keypads = data.keypad_data.keypads
    lutron_device_id = list(keypads)[0]
    keypad = keypads[lutron_device_id]
    device_id = keypad["dr_device_id"]

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
                        CONF_SUBTYPE: "on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )

    assert "value must be one of ['press', 'release']" in caplog.text


async def test_if_fires_on_button_event_late_setup(
    hass: HomeAssistant, calls, device_registry: dr.DeviceRegistry
) -> None:
    """Test for press trigger firing with integration getting setup late."""
    config_entry_id = await _async_setup_lutron_with_picos(hass)
    await hass.config_entries.async_unload(config_entry_id)
    await hass.async_block_till_done()

    device = MOCK_BUTTON_DEVICES[0]
    dr_device = device_registry.async_get_device(
        identifiers={(DOMAIN, device["serial"])}
    )
    device_id = dr_device.id

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
                        CONF_TYPE: "press",
                        CONF_SUBTYPE: "on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )

    await hass.config_entries.async_setup(config_entry_id)
    await hass.async_block_till_done()

    message = {
        ATTR_SERIAL: device.get("serial"),
        ATTR_TYPE: device.get("type"),
        ATTR_LEAP_BUTTON_NUMBER: 0,
        ATTR_DEVICE_NAME: device["Name"],
        ATTR_AREA_NAME: device.get("Area", {}).get("Name"),
        ATTR_ACTION: "press",
        ATTR_DEVICE_ID: device_id,
        ATTR_BUTTON_TYPE: "on",
    }
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_button_press"
