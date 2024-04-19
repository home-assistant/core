"""Test the WebOS Tv config flow."""

import dataclasses
from unittest.mock import Mock

from aiowebostv import WebOsTvPairError
import pytest

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.webostv.const import CONF_SOURCES, DOMAIN, LIVE_TV_APP_ID
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_webostv
from .const import CLIENT_KEY, FAKE_UUID, HOST, MOCK_APPS, MOCK_INPUTS, TV_NAME

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_USER_CONFIG = {
    CONF_HOST: HOST,
    CONF_NAME: TV_NAME,
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


async def test_form(hass: HomeAssistant, client) -> None:
    """Test we get the form."""
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TV_NAME


@pytest.mark.parametrize(
    ("apps", "inputs"),
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
async def test_options_flow_live_tv_in_apps(
    hass: HomeAssistant, client, apps, inputs
) -> None:
    """Test options config flow Live TV found in apps."""
    client.apps = apps
    client.inputs = inputs
    entry = await setup_webostv(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["Live TV", "Input01", "Input02"]},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_SOURCES] == ["Live TV", "Input01", "Input02"]


async def test_options_flow_cannot_retrieve(hass: HomeAssistant, client) -> None:
    """Test options config flow cannot retrieve sources."""
    entry = await setup_webostv(hass)

    client.connect = Mock(side_effect=ConnectionRefusedError())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_retrieve"}


async def test_form_cannot_connect(hass: HomeAssistant, client) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )

    client.connect = Mock(side_effect=ConnectionRefusedError())
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_pairexception(hass: HomeAssistant, client) -> None:
    """Test pairing exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )

    client.connect = Mock(side_effect=WebOsTvPairError("error"))
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "error_pairing"


async def test_entry_already_configured(hass: HomeAssistant, client) -> None:
    """Test entry already configured."""
    await setup_webostv(hass)
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_ssdp(hass: HomeAssistant, client) -> None:
    """Test that the ssdp confirmation form is served."""
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"


async def test_ssdp_in_progress(hass: HomeAssistant, client) -> None:
    """Test abort if ssdp paring is already in progress."""
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


async def test_ssdp_update_uuid(hass: HomeAssistant, client) -> None:
    """Test that ssdp updates existing host entry uuid."""
    entry = await setup_webostv(hass, None)
    assert client
    assert entry.unique_id is None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == MOCK_DISCOVERY_INFO.upnp[ssdp.ATTR_UPNP_UDN][5:]


async def test_ssdp_not_update_uuid(hass: HomeAssistant, client) -> None:
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

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pairing"
    assert entry.unique_id is None


async def test_form_abort_uuid_configured(hass: HomeAssistant, client) -> None:
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

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "new_host"


async def test_reauth_successful(hass: HomeAssistant, client, monkeypatch) -> None:
    """Test that the reauthorization is successful."""
    entry = await setup_webostv(hass)
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert entry.data[CONF_CLIENT_SECRET] == CLIENT_KEY

    monkeypatch.setattr(client, "client_key", "new_key")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_CLIENT_SECRET] == "new_key"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (WebOsTvPairError, "error_pairing"),
        (ConnectionRefusedError, "reauth_unsuccessful"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, client, monkeypatch, side_effect, reason
) -> None:
    """Test reauthorization errors."""
    entry = await setup_webostv(hass)
    assert client

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    monkeypatch.setattr(client, "connect", Mock(side_effect=side_effect))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
