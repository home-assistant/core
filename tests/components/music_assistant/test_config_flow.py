"""Define tests for the Music Assistant Integration config flow."""

from copy import deepcopy
from ipaddress import ip_address
from unittest import mock
from unittest.mock import AsyncMock

from music_assistant_client.exceptions import (
    CannotConnect,
    InvalidServerVersion,
    MusicAssistantClientException,
)
from music_assistant_models.api import ServerInfoMessage
import pytest

from homeassistant.components.music_assistant.config_flow import CONF_URL
from homeassistant.components.music_assistant.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, async_load_fixture

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
    properties=SERVER_INFO,
)


async def test_full_flow(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://localhost:8095"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_URL: "http://localhost:8095",
    }
    assert result["result"].unique_id == "1234"


async def test_zero_conf_missing_server_id(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf flow with missing server id."""
    bad_zero_conf_data = deepcopy(ZEROCONF_DATA)
    bad_zero_conf_data.properties.pop("server_id")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=bad_zero_conf_data,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_server_id"


async def test_duplicate_user(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate user flow."""
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
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate zeroconf flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (InvalidServerVersion("invalid_server_version"), "invalid_server_version"),
        (CannotConnect("cannot_connect"), "cannot_connect"),
        (MusicAssistantClientException("unknown"), "unknown"),
    ],
)
async def test_flow_user_server_version_invalid(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    exception: MusicAssistantClientException,
    error_message: str,
) -> None:
    """Test user flow when server url is invalid."""
    mock_get_server_info.side_effect = exception

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
    assert result["errors"] == {"base": error_message}

    mock_get_server_info.side_effect = None
    mock_get_server_info.return_value = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )

    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://localhost:8095"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_zeroconf_connect_issue(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf flow when server connect be reached."""
    mock_get_server_info.side_effect = CannotConnect("cannot_connect")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_url_different_from_server_base_url(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test that user-provided URL is used even when different from server base_url."""
    # Mock server info with a different base_url than what user will provide
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.base_url = "http://different-server:8095"
    mock_get_server_info.return_value = server_info

    user_url = "http://user-provided-server:8095"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: user_url},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    # Verify that the user-provided URL is stored, not the server's base_url
    assert result["data"] == {
        CONF_URL: user_url,
    }
    assert result["result"].unique_id == "1234"


async def test_duplicate_user_with_different_urls(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test duplicate detection works with different user URLs."""
    # Set up existing config entry with one URL
    existing_url = "http://existing-server:8095"
    existing_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Assistant",
        data={CONF_URL: existing_url},
        unique_id="1234",
    )
    existing_config_entry.add_to_hass(hass)

    # Mock server info with different base_url
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.base_url = "http://server-reported-url:8095"
    mock_get_server_info.return_value = server_info

    # Try to configure with a different user URL but same server_id
    new_user_url = "http://new-user-url:8095"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: new_user_url},
    )
    await hass.async_block_till_done()

    # Should detect as duplicate because server_id is the same
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_existing_entry_working_url(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf flow when existing entry has working URL."""
    mock_config_entry.add_to_hass(hass)

    # Mock server info with different base_url
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.base_url = "http://different-discovered-url:8095"
    mock_get_server_info.return_value = server_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DATA,
    )
    await hass.async_block_till_done()

    # Should abort because current URL is working
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Verify the URL was not changed
    assert mock_config_entry.data[CONF_URL] == "http://localhost:8095"


async def test_zeroconf_existing_entry_broken_url(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf flow when existing entry has broken URL."""
    mock_config_entry.add_to_hass(hass)

    # Create modified zeroconf data with different base_url
    modified_zeroconf_data = deepcopy(ZEROCONF_DATA)
    modified_zeroconf_data.properties["base_url"] = "http://discovered-working-url:8095"

    # Mock server info with the discovered URL
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.base_url = "http://discovered-working-url:8095"
    mock_get_server_info.return_value = server_info

    # First call (testing current URL) should fail, second call (testing discovered URL) should succeed
    mock_get_server_info.side_effect = [
        CannotConnect("cannot_connect"),  # Current URL fails
        server_info,  # Discovered URL works
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=modified_zeroconf_data,
    )
    await hass.async_block_till_done()

    # Should proceed to discovery confirm because current URL is broken
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    # Verify the URL was updated in the config entry
    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_URL] == "http://discovered-working-url:8095"


async def test_zeroconf_existing_entry_ignored(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf flow when existing entry was ignored."""
    # Create an ignored config entry (no URL field)
    ignored_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Assistant",
        data={},  # No URL field for ignored entries
        unique_id="1234",
        source=SOURCE_IGNORE,
    )
    ignored_config_entry.add_to_hass(hass)

    # Mock server info with discovered URL
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.base_url = "http://discovered-url:8095"
    mock_get_server_info.return_value = server_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DATA,
    )
    await hass.async_block_till_done()

    # Should abort because entry was ignored (respect user's choice)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Verify the ignored entry was not modified
    ignored_entry = hass.config_entries.async_get_entry(ignored_config_entry.entry_id)
    assert ignored_entry.data == {}  # Still no URL field
    assert ignored_entry.source == SOURCE_IGNORE
