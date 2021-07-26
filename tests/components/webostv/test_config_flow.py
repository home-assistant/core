"""Test the WebOS Tv config flow."""
from unittest.mock import Mock, patch

from aiopylgtv import PyLGTVPairException

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.webostv.const import CONF_SOURCES, DOMAIN
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

MOCK_DISCOVERY_INFO = {
    ssdp.ATTR_SSDP_LOCATION: "http://1.2.3.4",
    ssdp.ATTR_UPNP_FRIENDLY_NAME: "LG Webostv",
    ssdp.ATTR_UPNP_UDN: "uuid:some-fake-uuid",
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
    assert result["title"] == "fake"


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
        user_input={CONF_SOURCES: ["Input01", "Input02"]},
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"][CONF_SOURCES] == ["Input01", "Input02"]

    client.connect = Mock(side_effect=ConnectionRefusedError())
    result3 = await hass.config_entries.options.async_init(entry.entry_id)

    await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_FORM
    assert result3["errors"] == {"base": "cannot_retrieve"}


async def test_form_cannot_connect(hass, client):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )

    client.connect = Mock(side_effect=ConnectionRefusedError())
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


async def test_entry_already_configured(hass, client):
    """Test entry already configured."""
    await setup_webostv(hass)
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_form_ssdp(hass, client):
    """Test that the ssdp confirmation form is served."""
    assert client

    with patch("homeassistant.components.webostv.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
        )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pairing"


async def test_ssdp_in_progress(hass, client):
    """Test abort if ssdp paring is already in progress."""
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "pairing"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_in_progress"


async def test_ssdp_update_uuid(hass, client):
    """Test that ssdp updates existing host entry uuid."""
    entry = await setup_webostv(hass)
    assert client
    assert entry.unique_id is None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == MOCK_DISCOVERY_INFO[ssdp.ATTR_UPNP_UDN][5:]


async def test_ssdp_not_update_uuid(hass, client):
    """Test that ssdp not updates different host."""
    entry = await setup_webostv(hass)
    assert client
    assert entry.unique_id is None

    discovery_info = MOCK_DISCOVERY_INFO.copy()
    discovery_info.update({ssdp.ATTR_SSDP_LOCATION: "http://1.2.3.5"})

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "pairing"
    assert entry.unique_id is None
