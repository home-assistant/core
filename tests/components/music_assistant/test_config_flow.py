"""Define tests for the Music Assistant Integration config flow."""

from copy import deepcopy
from ipaddress import ip_address
from unittest import mock
from unittest.mock import AsyncMock

from music_assistant.client.exceptions import CannotConnect, InvalidServerVersion

from homeassistant.components.music_assistant import config_flow
from homeassistant.components.music_assistant.config_flow import CONF_URL
from homeassistant.components.music_assistant.const import DOMAIN

# pylint: disable=wrong-import-order
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DEFAULT_TITLE = "Music Assistant"

VALID_CONFIG = {
    CONF_URL: "http://localhost:8095",
}

SERVER_INFO = {
    "server_id": "1234",
    "base_url": "http://localhost:8095",
    "server_version": "0.0.0",
    "schema_version": 23,
    "min_supported_schema_version": 23,
    "homeassistant_addon": True,
}

ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="mock_hostname",
    port=None,
    type=mock.ANY,
    name=mock.ANY,
    properties={
        "server_id": "1234",
        "base_url": "http://localhost:8095",
        "server_version": "0.0.0",
        "schema_version": 23,
        "min_supported_schema_version": 23,
        "homeassistant_addon": True,
    },
)


# pylint: disable=dangerous-default-value
async def setup_music_assistant_integration(
    hass: HomeAssistant,
    *,
    config=VALID_CONFIG,
    options=None,
    entry_id="1",
    unique_id="1234",
    source="user",
):
    """Create the Music Assistant integration."""
    if options is None:
        options = {}
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=source,
        data=deepcopy(config),
        options=deepcopy(options),
        entry_id=entry_id,
        unique_id=unique_id,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_full_flow(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://localhost:8095"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Music Assistant"
    assert result["data"] == {
        CONF_URL: "http://localhost:8095",
    }
    assert result["result"].unique_id == "1234"


async def test_zero_conf_flow(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://localhost:8095"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Music Assistant"
    assert result["data"] == {
        CONF_URL: "http://localhost:8095",
    }
    assert result["result"].unique_id == "1234"


async def test_duplicate_manual(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://localhost:8095"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_zeroconf(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_init_connect_issue(
    mock_get_server_info, hass: HomeAssistant
) -> None:
    """Test we advance to the next step when server url is invalid."""
    mock_get_server_info.side_effect = CannotConnect("cannot_connect")

    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"], user_input={CONF_URL: "bad"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_init_server_version_invalid(
    mock_get_server_info, hass: HomeAssistant
) -> None:
    """Test we advance to the next step when server url is invalid."""
    mock_get_server_info.side_effect = InvalidServerVersion("invalid_server_version")

    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"], user_input={CONF_URL: "bad"}
    )
    assert result["errors"] == {"base": "invalid_server_version"}


async def test_flow_discovery_confirm_creates_config_entry(
    mock_get_server_info: AsyncMock, mock_music_assistant_client, hass: HomeAssistant
) -> None:
    """Test the config entry is successfully created."""
    config_flow.ConfigFlow.data = VALID_CONFIG
    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "zeroconf"}, data=ZEROCONF_DATA
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"],
    )
    expected = {
        "type": "form",
        "flow_id": mock.ANY,
        "handler": "music_assistant",
        "data_schema": None,
        "errors": None,
        "description_placeholders": {"url": "http://localhost:8095"},
        "last_step": None,
        "preview": None,
        "step_id": "discovery_confirm",
    }
    assert expected == result
