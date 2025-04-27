"""Test the LG webOS TV config flow."""

from aiowebostv import WebOsTvPairError
import pytest

from homeassistant import config_entries
from homeassistant.components.webostv.const import CONF_SOURCES, DOMAIN, LIVE_TV_APP_ID
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

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

MOCK_DISCOVERY_INFO = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=f"http://{HOST}",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: f"[LG] webOS TV {TV_MODEL}",
        ATTR_UPNP_UDN: f"uuid:{FAKE_UUID}",
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
    client.tv_state.apps = apps
    client.tv_state.inputs = inputs
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


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (WebOsTvPairError, "error_pairing"),
        (ConnectionResetError, "cannot_connect"),
    ],
)
async def test_options_flow_errors(
    hass: HomeAssistant, client, side_effect, error
) -> None:
    """Test options config flow errors."""
    entry = await setup_webostv(hass)

    client.connect.side_effect = side_effect
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # recover
    client.connect.side_effect = None
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

    client.connect.side_effect = ConnectionResetError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # recover
    client.connect.side_effect = None
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

    client.connect.side_effect = WebOsTvPairError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "error_pairing"}

    # recover
    client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TV_NAME


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
    entry = await setup_webostv(hass, MOCK_DISCOVERY_INFO.upnp[ATTR_UPNP_UDN][5:])
    assert entry.unique_id == MOCK_DISCOVERY_INFO.upnp[ATTR_UPNP_UDN][5:]
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


async def test_reauth_successful(hass: HomeAssistant, client) -> None:
    """Test that the reauthorization is successful."""
    entry = await setup_webostv(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert entry.data[CONF_CLIENT_SECRET] == CLIENT_KEY

    client.client_key = "new_key"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_CLIENT_SECRET] == "new_key"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (WebOsTvPairError, "error_pairing"),
        (ConnectionResetError, "cannot_connect"),
    ],
)
async def test_reauth_errors(hass: HomeAssistant, client, side_effect, error) -> None:
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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_successful(hass: HomeAssistant, client) -> None:
    """Test that the reconfigure is successful."""
    entry = await setup_webostv(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "new_host"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "new_host"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (WebOsTvPairError, "error_pairing"),
        (ConnectionResetError, "cannot_connect"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant, client, side_effect, error
) -> None:
    """Test reconfigure errors."""
    entry = await setup_webostv(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    client.connect.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "new_host"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "new_host"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_wrong_device(hass: HomeAssistant, client) -> None:
    """Test abort if reconfigure host is wrong webOS TV device."""
    entry = await setup_webostv(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    client.tv_info.hello = {"deviceUUID": "wrong_uuid"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "new_host"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
