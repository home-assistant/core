"""Test the WebOS Tv config flow."""

from unittest.mock import AsyncMock

from aiowebostv import WebOsTvPairError
import pytest

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.webostv.const import CONF_SOURCES, DOMAIN, LIVE_TV_APP_ID
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_webostv
from .const import (
    CLIENT_KEY,
    FAKE_UUID,
    HOST,
    MOCK_APPS,
    MOCK_INPUTS,
    TV_MODEL,
    TV_NAME,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_USER_CONFIG = {CONF_HOST: HOST}

MOCK_DISCOVERY_INFO = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=f"http://{HOST}",
    upnp={
        ssdp.ATTR_UPNP_FRIENDLY_NAME: f"[LG] webOS TV {TV_MODEL}",
        ssdp.ATTR_UPNP_UDN: f"uuid:{FAKE_UUID}",
    },
)


async def test_form(hass: HomeAssistant, client) -> None:
    """Test successful user flow."""
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TV_NAME
    config_entry = result["result"]
    assert config_entry.unique_id == FAKE_UUID


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

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["Live TV", "Input01", "Input02"]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SOURCES] == ["Live TV", "Input01", "Input02"]


async def test_options_flow_cannot_retrieve(hass: HomeAssistant, client) -> None:
    """Test options config flow cannot retrieve sources."""
    entry = await setup_webostv(hass)

    client.connect = AsyncMock(side_effect=ConnectionRefusedError())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_retrieve"}

    # recover
    client.connect = AsyncMock(return_value=True)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["Input01", "Input02"]},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_SOURCES] == ["Input01", "Input02"]


async def test_form_cannot_connect(hass: HomeAssistant, client) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )

    client.connect = AsyncMock(side_effect=ConnectionRefusedError())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # recover
    client.connect = AsyncMock(return_value=True)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TV_NAME


async def test_form_pairexception(hass: HomeAssistant, client) -> None:
    """Test pairing exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )

    client.connect = AsyncMock(side_effect=WebOsTvPairError("error"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "error_pairing"


async def test_entry_already_configured(hass: HomeAssistant, client) -> None:
    """Test entry already configured."""
    await setup_webostv(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_ssdp(hass: HomeAssistant, client) -> None:
    """Test that the ssdp confirmation form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TV_NAME
    config_entry = result["result"]
    assert config_entry.unique_id == FAKE_UUID


async def test_ssdp_in_progress(hass: HomeAssistant, client) -> None:
    """Test abort if ssdp paring is already in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data=MOCK_USER_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing"

    # Start another ssdp flow to make sure it aborts as already in progress
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=MOCK_DISCOVERY_INFO
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_form_abort_uuid_configured(hass: HomeAssistant, client) -> None:
    """Test abort if uuid is already configured, verify host update."""
    entry = await setup_webostv(hass, MOCK_DISCOVERY_INFO.upnp[ssdp.ATTR_UPNP_UDN][5:])
    assert entry.unique_id == MOCK_DISCOVERY_INFO.upnp[ssdp.ATTR_UPNP_UDN][5:]
    assert entry.data[CONF_HOST] == HOST

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    user_config = {CONF_HOST: "new_host"}

    # Start another flow to make sure it aborts and updates host
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "new_host"


async def test_reauth_successful(
    hass: HomeAssistant, client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that the reauthorization is successful."""
    entry = await setup_webostv(hass)

    result = await entry.start_reauth_flow(hass)
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
    hass: HomeAssistant, client, monkeypatch: pytest.MonkeyPatch, side_effect, reason
) -> None:
    """Test reauthorization errors."""
    entry = await setup_webostv(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    client.connect.side_effect = side_effect()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
