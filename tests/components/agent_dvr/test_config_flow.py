"""Tests for the Agent DVR config flow."""

import pytest
from pytest_homeassistant.common import async_load_fixture
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.agent_dvr.const import DOMAIN, SERVER_URL
from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from . import create_entry, init_integration

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

APP_SERVER_URL = "http://127.0.0.1:8090/"

# What Agent DVR answers when it refuses a request, e.g. with Protect API on
REFUSED = '{"error": "This server is protected"}'

HASSIO_DISCOVERY = HassioServiceInfo(
    config={"addon": "Agent DVR", "host": "127.0.0.1", "port": 8090},
    name="Agent DVR",
    slug="a910219e_agentdvr",
    uuid="1234",
)


@pytest.fixture
async def mock_agent_app(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Mock the Agent DVR server run by the Agent DVR app."""
    aioclient_mock.get(
        f"{APP_SERVER_URL}command.cgi?cmd=getStatus",
        text=await async_load_fixture(hass, "status.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"{APP_SERVER_URL}command.cgi?cmd=getObjects",
        text=await async_load_fixture(hass, "objects.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort flow if Agent device already configured."""
    await init_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "example.local", CONF_PORT: 8090},
    )

    assert result["type"] is FlowResultType.ABORT


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on Agent connection error."""

    aioclient_mock.get("http://example.local:8090/command.cgi?cmd=getStatus", text="")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "example.local", CONF_PORT: 8090},
    )

    assert result["errors"]["base"] == "cannot_connect"
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getStatus",
        text=await async_load_fixture(hass, "status.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getObjects",
        text=await async_load_fixture(hass, "objects.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "example.local", CONF_PORT: 8090},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_server_refuses(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a server that refuses the request, e.g. with Protect API on."""
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getStatus",
        text=REFUSED,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "example.local", CONF_PORT: 8090},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getStatus",
        text=await async_load_fixture(hass, "status.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "example.local", CONF_PORT: 8090},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getStatus",
        text=await async_load_fixture(hass, "status.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        "http://example.local:8090/command.cgi?cmd=getObjects",
        text=await async_load_fixture(hass, "objects.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "example.local", CONF_PORT: 8090}
    )

    assert result["data"][CONF_HOST] == "example.local"
    assert result["data"][CONF_PORT] == 8090
    assert result["data"][SERVER_URL] == "http://example.local:8090/"
    assert result["title"] == "DESKTOP"
    assert result["type"] is FlowResultType.CREATE_ENTRY

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].unique_id == "c0715bba-c2d0-48ef-9e3e-bc81c9ea4447"


@pytest.mark.usefixtures("mock_agent_app")
async def test_hassio_discovery(hass: HomeAssistant) -> None:
    """Test the Agent DVR app is set up after confirming its discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DISCOVERY
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Agent DVR"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "DESKTOP"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 8090,
        SERVER_URL: APP_SERVER_URL,
    }
    assert result["result"].unique_id == "c0715bba-c2d0-48ef-9e3e-bc81c9ea4447"


@pytest.mark.usefixtures("mock_agent_app")
async def test_hassio_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test discovery updates a server that was already added by hand."""
    entry = create_entry(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 8090,
        SERVER_URL: APP_SERVER_URL,
    }


@pytest.mark.usefixtures("mock_agent_app")
async def test_user_flow_with_hassio_discovery_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test adding the server by hand while its discovery waits replaces it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 8090}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "c0715bba-c2d0-48ef-9e3e-bc81c9ea4447"
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize(
    "response",
    [
        {"text": ""},
        {"text": REFUSED, "headers": {"Content-Type": CONTENT_TYPE_JSON}},
    ],
    ids=["unreachable", "refused"],
)
async def test_hassio_discovery_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, response: dict
) -> None:
    """Test discovery aborts when the Agent DVR app's server can't be used."""
    aioclient_mock.get(f"{APP_SERVER_URL}command.cgi?cmd=getStatus", **response)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
