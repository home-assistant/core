"""Test the Roku config flow."""
from asynctest import patch

from homeassistant.components.roku.const import DOMAIN
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.setup import async_setup_component

HOST = "1.2.3.4"
NAME = "Roku 3"
SSDP_LOCATION = "http://1.2.3.4/"
UPNP_FRIENDLY_NAME = "My Roku 3"
UPNP_SERIAL = "1GU48T017973"

MOCK_DATA_DEVICE_INFO = {
    "model_name": NAME,
    "model_num": "4200X",
    "software_version": "7.5.0.09021",
    "serial_num": UPNP_SERIAL,
    "user_device_name": UPNP_FRIENDLY_NAME,
    "roku_type": "Box",
}


async def test_step_user(hass):
    """Test the user step."""
    await async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.roku.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.roku.async_setup_entry", return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.roku.config_flow.Roku.device_info",
        return_value=MOCK_DATA_DEVICE_INFO,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST},
        )

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == HOST
    assert result2["data"] == {
        CONF_HOST: HOST,
        CONF_NAME: HOST,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_step_import(hass):
    """Test the import step."""
    with patch(
        "homeassistant.components.roku.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.roku.async_setup_entry", return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.roku.config_flow.Roku.device_info",
        return_value=MOCK_DATA_DEVICE_INFO,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: HOST},
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_NAME: HOST,
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_step_ssdp(hass):
    """Test the ssdp discovery step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data={
            ATTR_SSDP_LOCATION: SSDP_LOCATION,
            ATTR_UPNP_FRIENDLY_NAME: UPNP_FRIENDLY_NAME,
            ATTR_UPNP_SERIAL: UPNP_SERIAL,
        },
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "ssdp_confirm"
    assert result["description_placeholders"] == {CONF_NAME: UPNP_FRIENDLY_NAME}

    with patch(
        "homeassistant.components.roku.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.roku.async_setup_entry", return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.roku.config_flow.Roku.device_info",
        return_value=MOCK_DATA_DEVICE_INFO,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == UPNP_FRIENDLY_NAME
    assert result2["data"] == {
        CONF_HOST: HOST,
        CONF_NAME: UPNP_FRIENDLY_NAME,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
