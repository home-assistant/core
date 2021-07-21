"""Test the WebOS Tv config flow."""
from unittest.mock import Mock, patch

from aiopylgtv import PyLGTVPairException

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.webostv import CannotConnect
from homeassistant.components.webostv.const import CONF_ON_ACTION, CONF_SOURCES, DOMAIN
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import CONF_HOST, CONF_ICON, CONF_NAME, CONF_SOURCE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import setup_webostv

MOCK_YAML_CONFIG = {
    CONF_HOST: "1.2.3.4",
    CONF_NAME: "fake",
    CONF_ICON: "mdi:test",
}


async def test_form_import(hass, client):
    """Test we can import yaml config."""
    assert client

    with patch("homeassistant.components.webostv.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_IMPORT},
            data=MOCK_YAML_CONFIG,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "fake"


async def test_form(hass, client):
    """Test we get the form."""
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pairing"

    with patch("homeassistant.components.webostv.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["name"] == "fake"


async def test_options_flow(hass, client):
    """Test options config flow."""
    entry = await setup_webostv(hass)

    hass.states.async_set("script.test", "off", {"domain": "script"})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ON_ACTION: "script.test",
            CONF_SOURCES: ["Input01", "Input02"],
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"][CONF_ON_ACTION] == "script.test"

    client.connect = Mock(side_effect=CannotConnect("error"))
    result3 = await hass.config_entries.options.async_init(entry.entry_id)

    await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_FORM
    assert result3["errors"] == {"base": "cannot_retrieve"}


async def test_options_script_incorrect_flow(hass, client):
    """Test json format incorrect in options config flow."""
    entry = await setup_webostv(hass)
    assert client

    hass.states.async_set("script.fake", "off", {"domain": "script"})

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ON_ACTION: "script.test"},
    )

    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "script_not_found"}

    hass.states.async_set("fake.test", "off", {"domain": "fake"})

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ON_ACTION: "fake.test"},
    )

    await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_FORM
    assert result3["errors"] == {"base": "script_not_found"}


async def test_form_cannot_connect(hass, client):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )

    client.connect = Mock(side_effect=CannotConnect("error"))
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_pairexception(hass, client):
    """Test pairing exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )

    client.connect = Mock(side_effect=PyLGTVPairException("error"))
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "error_pairing"


async def test_form_updates_unique_id(hass, client):
    """Test duplicated unique_id."""
    await setup_webostv(hass)
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pairing"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"


async def test_form_ssdp(hass, client):
    """Test that the ssdp confirmation form is served."""
    assert client

    discovery_info = {
        ssdp.ATTR_SSDP_LOCATION: "http://hostname",
        ssdp.ATTR_UPNP_FRIENDLY_NAME: "LG Webostv",
    }

    with patch("homeassistant.components.webostv.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
        )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "LG Webostv"


async def test_pairing_failed_form(hass, client):
    """Test pairing form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pairing"

    client.is_registered.return_value = False
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"


async def test_client_key_missing(hass, client):
    """Test abort if missing client key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pairing"

    client.is_registered.return_value = True
    client.client_key = None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "client_key_not_found"
