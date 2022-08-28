"""The tests for Lutron Caséta device triggers."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.lutron_caseta import (
    ATTR_ACTION,
    ATTR_AREA_NAME,
    ATTR_DEVICE_NAME,
    ATTR_SERIAL,
    ATTR_TYPE,
)
from homeassistant.components.lutron_caseta.const import (
    ATTR_LEAP_BUTTON_NUMBER,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
    MANUFACTURER,
)
from homeassistant.components.lutron_caseta.device_trigger import CONF_SUBTYPE
from homeassistant.components.lutron_caseta.models import LutronCasetaData
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
)

MOCK_BUTTON_DEVICES = [
    {
        "Name": "Back Hall Pico",
        "ID": 2,
        "Area": {"Name": "Back Hall"},
        "Buttons": [
            {"Number": 2},
            {"Number": 3},
            {"Number": 4},
            {"Number": 5},
            {"Number": 6},
        ],
        "leap_name": "Back Hall_Back Hall Pico",
        "type": "Pico3ButtonRaiseLower",
        "model": "PJ2-3BRL-GXX-X01",
        "serial": 43845548,
    },
    {
        "Name": "Front Steps Sunnata Keypad",
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
        "serial": 43845547,
    },
]


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


async def _async_setup_lutron_with_picos(hass, device_reg):
    """Setups a lutron bridge with picos."""
    await async_setup_component(hass, DOMAIN, {})

    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    dr_button_devices = {}

    for device in MOCK_BUTTON_DEVICES:
        dr_device = device_reg.async_get_or_create(
            name=device["leap_name"],
            manufacturer=MANUFACTURER,
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, device["serial"])},
            model=f"{device['model']} ({device[CONF_TYPE]})",
        )
        dr_button_devices[dr_device.id] = device

    hass.data[DOMAIN][config_entry.entry_id] = LutronCasetaData(
        MagicMock(), MagicMock(), dr_button_devices
    )
    return config_entry.entry_id


async def test_get_triggers(hass, device_reg):
    """Test we get the expected triggers from a lutron pico."""
    config_entry_id = await _async_setup_lutron_with_picos(hass, device_reg)
    data: LutronCasetaData = hass.data[DOMAIN][config_entry_id]
    dr_button_devices = data.button_devices
    device_id = list(dr_button_devices)[0]

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
    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_for_invalid_device_id(hass, device_reg):
    """Test error raised for invalid lutron device_id."""
    config_entry_id = await _async_setup_lutron_with_picos(hass, device_reg)

    invalid_device = device_reg.async_get_or_create(
        config_entry_id=config_entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, invalid_device.id
        )


async def test_if_fires_on_button_event(hass, calls, device_reg):
    """Test for press trigger firing."""
    await _async_setup_lutron_with_picos(hass, device_reg)
    device = MOCK_BUTTON_DEVICES[0]
    dr = device_registry.async_get(hass)
    dr_device = dr.async_get_device(identifiers={(DOMAIN, device["serial"])})
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
    }
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_button_press"


async def test_if_fires_on_button_event_without_lip(hass, calls, device_reg):
    """Test for press trigger firing on a device that does not support lip."""
    await _async_setup_lutron_with_picos(hass, device_reg)
    device = MOCK_BUTTON_DEVICES[1]
    dr = device_registry.async_get(hass)
    dr_device = dr.async_get_device(identifiers={(DOMAIN, device["serial"])})
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
                        CONF_SUBTYPE: "button_1",
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
        ATTR_LEAP_BUTTON_NUMBER: 1,
        ATTR_DEVICE_NAME: device["Name"],
        ATTR_AREA_NAME: device.get("Area", {}).get("Name"),
        ATTR_ACTION: "press",
    }
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_button_press"


async def test_validate_trigger_config_no_device(hass, calls, device_reg):
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


async def test_validate_trigger_config_unknown_device(hass, calls, device_reg):
    """Test for no press with an unknown device."""

    config_entry_id = await _async_setup_lutron_with_picos(hass, device_reg)
    data: LutronCasetaData = hass.data[DOMAIN][config_entry_id]
    dr_button_devices = data.button_devices
    device_id = list(dr_button_devices)[0]
    device = dr_button_devices[device_id]
    device["type"] = "unknown"

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


async def test_validate_trigger_invalid_triggers(hass, device_reg):
    """Test for click_event with invalid triggers."""
    config_entry_id = await _async_setup_lutron_with_picos(hass, device_reg)
    data: LutronCasetaData = hass.data[DOMAIN][config_entry_id]
    dr_button_devices = data.button_devices
    device_id = list(dr_button_devices)[0]
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
