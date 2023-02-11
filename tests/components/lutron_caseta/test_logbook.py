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
from homeassistant.setup import async_setup_component

from . import MockBridge

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
