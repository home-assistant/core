"""Test the DirecTV config flow."""
from asynctest import patch

from homeassistant.components.directv.config_flow import CannotConnect
from homeassistant.components.directv.const import DOMAIN
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME, CONF_SOURCE
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.setup import async_setup_component

HOST = "1.1.1.1"
NAME = "DirecTV Receiver"
SSDP_LOCATION = "http://1.1.1.1/"

MOCK_GET_VERSION = {
    "accessCardId": "0021-1495-6572",
    "receiverId": "0288 7745 5858",
    "status": {
        "code": 200,
        "commandResult": 0,
        "msg": "OK.",
        "query": "/info/getVersion",
    },
    "stbSoftwareVersion": "0x4ed7",
    "systemTime": 1281625203,
    "version": "1.2",
}


async def test_form(hass):
    """Test we get the form."""
    await async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.directv.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.directv.async_setup_entry", return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.directv.config_flow.DIRECTV.get_version",
        return_value=MOCK_GET_VERSION,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST,},
        )

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == NAME
    assert result2["data"] == {
        CONF_HOST: HOST,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    with patch(
        "homeassistant.components.directv.DIRECTV.get_version",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST,},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import(hass):
    """Test the import step."""
    with patch(
        "homeassistant.components.directv.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.directv.async_setup_entry", return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.directv.DIRECTV.get_version",
        return_value=MOCK_GET_VERSION,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data={CONF_HOST: HOST},
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_IP_ADDRESS: HOST,
        CONF_NAME: HOST,
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_discovery(hass):
    """Test the ssdp discovery step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data={ATTR_SSDP_LOCATION: SSDP_LOCATION,},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "ssdp_confirm"
    assert result["description_placeholders"] == {CONF_NAME: NAME}

    with patch(
        "homeassistant.components.directv.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.directv.async_setup_entry", return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.directv.DIRECTV.get_version",
        return_value=MOCK_GET_VERSION,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {},)

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == NAME
    assert result2["data"] == {
        CONF_HOST: HOST,
        CONF_IP_ADDRESS: HOST,
        CONF_NAME: NAME,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
