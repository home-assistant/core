"""The tests for Lutron Caséta device triggers."""
import pytest

from homeassistant import setup
from homeassistant.components import automation
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.lutron_caseta import (
    ATTR_ACTION,
    ATTR_AREA_NAME,
    ATTR_BUTTON_NUMBER,
    ATTR_DEVICE_NAME,
    ATTR_SERIAL,
    ATTR_TYPE,
)
from homeassistant.components.lutron_caseta.const import (
    BUTTON_DEVICES,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
    MANUFACTURER,
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
    }
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

    hass.data[DOMAIN][config_entry.entry_id] = {BUTTON_DEVICES: dr_button_devices}

    return config_entry.entry_id


async def test_get_triggers(hass, device_reg):
    """Test we get the expected triggers from a lutron pico."""
    config_entry_id = await _async_setup_lutron_with_picos(hass, device_reg)
    dr_button_devices = hass.data[DOMAIN][config_entry_id][BUTTON_DEVICES]
    device_id = list(dr_button_devices)[0]

    expected_triggers = [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "on",
            CONF_TYPE: "press",
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "stop",
            CONF_TYPE: "press",
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "off",
            CONF_TYPE: "press",
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "raise",
            CONF_TYPE: "press",
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "lower",
            CONF_TYPE: "press",
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "on",
            CONF_TYPE: "release",
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "stop",
            CONF_TYPE: "release",
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "off",
            CONF_TYPE: "release",
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "raise",
            CONF_TYPE: "release",
        },
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_PLATFORM: "device",
            CONF_SUBTYPE: "lower",
            CONF_TYPE: "release",
        },
    ]

    triggers = await async_get_device_automations(hass, "trigger", device_id)
    assert_lists_same(triggers, expected_triggers)


async def test_get_triggers_for_invalid_device_id(hass, device_reg):
    """Test error raised for invalid lutron device_id."""
    config_entry_id = await _async_setup_lutron_with_picos(hass, device_reg)

    invalid_device = device_reg.async_get_or_create(
        config_entry_id=config_entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_get_device_automations(hass, "trigger", invalid_device.id)


async def test_if_fires_on_button_event(hass, calls, device_reg):
    """Test for press trigger firing."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    config_entry_id = await _async_setup_lutron_with_picos(hass, device_reg)
    dr_button_devices = hass.data[DOMAIN][config_entry_id][BUTTON_DEVICES]
    device_id = list(dr_button_devices)[0]
    device = dr_button_devices[device_id]
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
        ATTR_BUTTON_NUMBER: 2,
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
        ATTR_BUTTON_NUMBER: 3,
        ATTR_DEVICE_NAME: "any",
        ATTR_AREA_NAME: "area",
        ATTR_ACTION: "press",
    }
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_validate_trigger_config_unknown_device(hass, calls, device_reg):
    """Test for no press with an unknown device."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    config_entry_id = await _async_setup_lutron_with_picos(hass, device_reg)
    dr_button_devices = hass.data[DOMAIN][config_entry_id][BUTTON_DEVICES]
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
        ATTR_BUTTON_NUMBER: 3,
        ATTR_DEVICE_NAME: "any",
        ATTR_AREA_NAME: "area",
        ATTR_ACTION: "press",
    }
    hass.bus.async_fire(LUTRON_CASETA_BUTTON_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_validate_trigger_invalid_triggers(hass, device_reg):
    """Test for click_event with invalid triggers."""
    notification_calls = async_mock_service(hass, "persistent_notification", "create")
    config_entry_id = await _async_setup_lutron_with_picos(hass, device_reg)
    dr_button_devices = hass.data[DOMAIN][config_entry_id][BUTTON_DEVICES]
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

    assert len(notification_calls) == 1
    assert (
        "The following integrations and platforms could not be set up"
        in notification_calls[0].data["message"]
    )
