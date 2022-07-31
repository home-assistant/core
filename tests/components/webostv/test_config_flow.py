"""Test the WebOS Tv config flow."""
import dataclasses
from unittest.mock import Mock, patch

from aiowebostv import WebOsTvPairError
import pytest

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.webostv.const import CONF_SOURCES, DOMAIN, LIVE_TV_APP_ID
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import (
    CONF_CLIENT_SECRET,
    CONF_HOST,
    CONF_ICON,
    CONF_NAME,
    CONF_SOURCE,
    CONF_UNIQUE_ID,
)
from homeassistant.data_entry_flow import FlowResultType

from . import setup_webostv
from .const import CLIENT_KEY, FAKE_UUID, HOST, MOCK_APPS, MOCK_INPUTS, TV_NAME

MOCK_YAML_CONFIG = {
    CONF_HOST: HOST,
    CONF_NAME: TV_NAME,
    CONF_ICON: "mdi:test",
    CONF_CLIENT_SECRET: CLIENT_KEY,
    CONF_UNIQUE_ID: FAKE_UUID,
}

MOCK_DISCOVERY_INFO = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=f"http://{HOST}",
    upnp={
        ssdp.ATTR_UPNP_FRIENDLY_NAME: "LG Webostv",
        ssdp.ATTR_UPNP_UDN: f"uuid:{FAKE_UUID}",
    },
)


async def test_form(hass, client):
    """Test we get the form."""
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pairing"

    with patch("homeassistant.components.webostv.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TV_NAME


@pytest.mark.parametrize(
    "apps, inputs",
    [
        # Live TV in apps (default)
        (MOCK_APPS, MOCK_INPUTS),
        # Live TV in inputs
        (
            {},
            {
                **MOCK_INPUTS,
                "livetv": {"label": "Live TV", "id": "livetv", "appId": LIVE_TV_APP_ID},
            },
        ),
        # Live TV not found
        ({}, MOCK_INPUTS),
    ],
)
async def test_options_flow_live_tv_in_apps(hass, client, apps, inputs):
    """Test options config flow Live TV found in apps."""
    client.apps = apps
    client.inputs = inputs
    entry = await setup_webostv(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["Live TV", "Input01", "Input02"]},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_SOURCES] == ["Live TV", "Input01", "Input02"]


async def test_options_flow_cannot_retrieve(hass, client):
    """Test options config flow cannot retrieve sources."""
    entry = await setup_webostv(hass)

    client.connect = Mock(side_effect=ConnectionRefusedError())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_retrieve"}


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

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_pairexception(hass, client):
    """Test pairing exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_YAML_CONFIG,
    )

    client.connect = Mock(side_effect=WebOsTvPairError("error"))
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
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

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_ssdp(hass, client):
    """Test that the ssdp confirmation form is served."""
    assert client

    with patch("homeassistant.components.webostv.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


async def test_ssdp_update_uuid(hass, client):
    """Test that ssdp updates existing host entry uuid."""
    entry = await setup_webostv(hass, None)
    assert client
    assert entry.unique_id is None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == MOCK_DISCOVERY_INFO.upnp[ssdp.ATTR_UPNP_UDN][5:]


async def test_ssdp_not_update_uuid(hass, client):
    """Test that ssdp not updates different host."""
    entry = await setup_webostv(hass, None)
    assert client
    assert entry.unique_id is None

    discovery_info = dataclasses.replace(MOCK_DISCOVERY_INFO)
    discovery_info.ssdp_location = "http://1.2.3.5"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "pairing"
    assert entry.unique_id is None


async def test_form_abort_uuid_configured(hass, client):
    """Test abort if uuid is already configured, verify host update."""
    entry = await setup_webostv(hass, MOCK_DISCOVERY_INFO.upnp[ssdp.ATTR_UPNP_UDN][5:])
    assert client
    assert entry.unique_id == MOCK_DISCOVERY_INFO.upnp[ssdp.ATTR_UPNP_UDN][5:]
    assert entry.data[CONF_HOST] == HOST

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    user_config = {
        CONF_HOST: "new_host",
        CONF_NAME: TV_NAME,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=user_config,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "new_host"
