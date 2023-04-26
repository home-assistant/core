"""The tests for lutron caseta logbook."""
from unittest.mock import patch

from homeassistant.components.lutron_caseta.const import (
    ATTR_ACTION,
    ATTR_AREA_NAME,
    ATTR_BUTTON_NUMBER,
    ATTR_DEVICE_NAME,
    ATTR_LEAP_BUTTON_NUMBER,
    ATTR_SERIAL,
    ATTR_TYPE,
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
)
from homeassistant.components.lutron_caseta.models import LutronCasetaData
from homeassistant.const import ATTR_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import MockBridge, async_setup_integration

from tests.common import MockConfigEntry
from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanify_lutron_caseta_button_event(hass: HomeAssistant) -> None:
    """Test humanifying lutron_caseta_button_events."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
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

    await hass.async_block_till_done()

    data: LutronCasetaData = hass.data[DOMAIN][config_entry.entry_id]
    keypads = data.keypad_data.keypads
    keypad = keypads["9"]
    dr_device_id = keypad["dr_device_id"]

    (event1,) = mock_humanify(
        hass,
        [
            MockRow(
                LUTRON_CASETA_BUTTON_EVENT,
                {
                    ATTR_SERIAL: "68551522",
                    ATTR_DEVICE_ID: dr_device_id,
                    ATTR_TYPE: "Pico3ButtonRaiseLower",
                    ATTR_LEAP_BUTTON_NUMBER: 1,
                    ATTR_BUTTON_NUMBER: 1,
                    ATTR_DEVICE_NAME: "Pico",
                    ATTR_AREA_NAME: "Dining Room",
                    ATTR_ACTION: "press",
                },
            ),
        ],
    )

    assert event1["name"] == "Dining Room Pico"
    assert event1["domain"] == DOMAIN
    assert event1["message"] == "press stop"


async def test_humanify_lutron_caseta_button_event_integration_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Test humanifying lutron_caseta_button_events when the integration fails to load."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
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

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    for device in device_registry.devices.values():
        if device.config_entries == {config_entry.entry_id}:
            dr_device_id = device.id
            break

    assert dr_device_id is not None
    (event1,) = mock_humanify(
        hass,
        [
            MockRow(
                LUTRON_CASETA_BUTTON_EVENT,
                {
                    ATTR_SERIAL: "68551522",
                    ATTR_DEVICE_ID: dr_device_id,
                    ATTR_TYPE: "Pico3ButtonRaiseLower",
                    ATTR_LEAP_BUTTON_NUMBER: 1,
                    ATTR_BUTTON_NUMBER: 1,
                    ATTR_DEVICE_NAME: "Pico",
                    ATTR_AREA_NAME: "Dining Room",
                    ATTR_ACTION: "press",
                },
            ),
        ],
    )

    assert event1["name"] == "Dining Room Pico"
    assert event1["domain"] == DOMAIN
    assert event1["message"] == "press stop"


async def test_humanify_lutron_caseta_button_event_ra3(hass: HomeAssistant) -> None:
    """Test humanifying lutron_caseta_button_events from an RA3 hub."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await async_setup_integration(hass, MockBridge)

    registry = dr.async_get(hass)
    keypad = registry.async_get_device(
        identifiers={(DOMAIN, 66286451)}, connections=set()
    )
    assert keypad

    (event1,) = mock_humanify(
        hass,
        [
            MockRow(
                LUTRON_CASETA_BUTTON_EVENT,
                {
                    ATTR_SERIAL: "66286451",
                    ATTR_DEVICE_ID: keypad.id,
                    ATTR_TYPE: keypad.model,
                    ATTR_LEAP_BUTTON_NUMBER: 3,
                    ATTR_BUTTON_NUMBER: 3,
                    ATTR_DEVICE_NAME: "Keypad",
                    ATTR_AREA_NAME: "Breakfast",
                    ATTR_ACTION: "press",
                },
            ),
        ],
    )

    assert event1["name"] == "Breakfast Keypad"
    assert event1["domain"] == DOMAIN
    assert event1["message"] == "press Kitchen Pendants"


async def test_humanify_lutron_caseta_button_unknown_type(hass: HomeAssistant) -> None:
    """Test humanifying lutron_caseta_button_events with an unknown type."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await async_setup_integration(hass, MockBridge)

    registry = dr.async_get(hass)
    keypad = registry.async_get_device(
        identifiers={(DOMAIN, 66286451)}, connections=set()
    )
    assert keypad

    (event1,) = mock_humanify(
        hass,
        [
            MockRow(
                LUTRON_CASETA_BUTTON_EVENT,
                {
                    ATTR_SERIAL: "66286451",
                    ATTR_DEVICE_ID: "removed",
                    ATTR_TYPE: keypad.model,
                    ATTR_LEAP_BUTTON_NUMBER: 3,
                    ATTR_BUTTON_NUMBER: 3,
                    ATTR_DEVICE_NAME: "Keypad",
                    ATTR_AREA_NAME: "Breakfast",
                    ATTR_ACTION: "press",
                },
            ),
        ],
    )

    assert event1["name"] == "Breakfast Keypad"
    assert event1["domain"] == DOMAIN
    assert event1["message"] == "press Error retrieving button description"
