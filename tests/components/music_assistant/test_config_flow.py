"""Define tests for the Music Assistant Integration config flow."""

from copy import deepcopy
from ipaddress import ip_address
from unittest import mock
from unittest.mock import AsyncMock, patch

from music_assistant_client.exceptions import (
    CannotConnect,
    InvalidServerVersion,
    MusicAssistantClientException,
)
from music_assistant_models.api import ServerInfoMessage
from music_assistant_models.errors import AuthenticationFailed, InvalidToken
import pytest

from homeassistant.components.music_assistant.config_flow import (
    CONF_URL,
    MusicAssistantConfigFlow,
    _get_server_info,
    _test_connection,
)
from homeassistant.components.music_assistant.const import (
    AUTH_SCHEMA_VERSION,
    CONF_TOKEN,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_HASSIO,
    SOURCE_IGNORE,
    SOURCE_REAUTH,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, async_load_fixture

SERVER_INFO = {
    "server_id": "1234",
    "base_url": "http://localhost:8095",
    "server_version": "0.0.0",
    "schema_version": AUTH_SCHEMA_VERSION,
    "min_supported_schema_version": AUTH_SCHEMA_VERSION,
    "homeassistant_addon": False,
    "onboard_done": True,
}

# Zeroconf discovery properties are always strings
ZEROCONF_PROPERTIES = {
    "server_id": "1234",
    "base_url": "http://localhost:8095",
    "server_version": "0.0.0",
    "schema_version": str(AUTH_SCHEMA_VERSION),
    "min_supported_schema_version": str(AUTH_SCHEMA_VERSION),
    "homeassistant_addon": "False",
    "onboard_done": "True",
}

ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="mock_hostname",
    port=None,
    type=mock.ANY,
    name=mock.ANY,
    properties=ZEROCONF_PROPERTIES,
)

HASSIO_DATA = HassioServiceInfo(
    config={"host": "addon-music-assistant", "port": 8094, "auth_token": "test_token"},
    name="Music Assistant",
    slug="music_assistant",
    uuid="1234",
)


async def test_full_flow(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test full flow with old schema (no auth required)."""
    # Mock an old server that doesn't require authentication
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.schema_version = AUTH_SCHEMA_VERSION - 1
    mock_get_server_info.return_value = server_info

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


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf flow with old schema (no auth required)."""
    # Use old schema version zeroconf data
    old_schema_zeroconf_data = deepcopy(ZEROCONF_DATA)
    old_schema_zeroconf_data.properties["schema_version"] = AUTH_SCHEMA_VERSION - 1
    old_schema_zeroconf_data.properties["min_supported_schema_version"] = (
        AUTH_SCHEMA_VERSION - 1
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=old_schema_zeroconf_data,
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


async def test_zeroconf_invalid_discovery_info(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf flow with invalid discovery info."""
    bad_zeroconf_data = deepcopy(ZEROCONF_DATA)
    bad_zeroconf_data.properties.pop("server_id")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=bad_zeroconf_data,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


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
    # Use old schema version (no auth required)
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.schema_version = AUTH_SCHEMA_VERSION - 1
    mock_get_server_info.return_value = server_info

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
    # Use old schema version (no auth required)
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.base_url = "http://different-server:8095"
    server_info.schema_version = AUTH_SCHEMA_VERSION - 1
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
    # Use old schema version (no auth required)
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.base_url = "http://server-reported-url:8095"
    server_info.schema_version = AUTH_SCHEMA_VERSION - 1
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
    # Use old schema version (no auth required)
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.base_url = "http://different-discovered-url:8095"
    server_info.schema_version = AUTH_SCHEMA_VERSION - 1
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
    # Use old schema version (no auth required)
    server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )
    server_info.base_url = "http://discovered-url:8095"
    server_info.schema_version = AUTH_SCHEMA_VERSION - 1
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


async def test_hassio_flow(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test hassio discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_HASSIO},
        data=HASSIO_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_URL: "http://addon-music-assistant:8094",
        CONF_TOKEN: "test_token",
    }
    assert result["result"].unique_id == "1234"


async def test_hassio_flow_duplicate(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test hassio discovery flow with duplicate server."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_HASSIO},
        data=HASSIO_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_hassio_flow_updates_failed_entry_and_reloads(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test hassio discovery updates entry in SETUP_ERROR state and schedules reload."""
    # Create an entry with old URL and token
    failed_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Assistant",
        data={CONF_URL: "http://old-url:8094", CONF_TOKEN: "old_token"},
        unique_id="1234",
    )
    failed_entry.add_to_hass(hass)

    # First, setup the entry with invalid auth to get it into SETUP_ERROR state
    with patch(
        "homeassistant.components.music_assistant.MusicAssistantClient"
    ) as mock_client:
        mock_client.return_value.connect.side_effect = AuthenticationFailed(
            "Invalid token"
        )
        await hass.config_entries.async_setup(failed_entry.entry_id)
        await hass.async_block_till_done()

    # Verify entry is in SETUP_ERROR state
    assert failed_entry.state is ConfigEntryState.SETUP_ERROR

    # Now trigger hassio discovery with valid token
    # Mock async_schedule_reload to prevent actual reload attempt
    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_HASSIO},
            data=HASSIO_DATA,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

        # Verify the entry was updated with new URL and token
        assert failed_entry.data[CONF_URL] == "http://addon-music-assistant:8094"
        assert failed_entry.data[CONF_TOKEN] == "test_token"

        # Verify reload was scheduled
        mock_schedule_reload.assert_called_once_with(failed_entry.entry_id)


@pytest.mark.parametrize(
    ("exception", "error_reason"),
    [
        (InvalidServerVersion("invalid_server_version"), "invalid_server_version"),
        (CannotConnect("cannot_connect"), "cannot_connect"),
        (MusicAssistantClientException("unknown"), "unknown"),
    ],
)
async def test_hassio_flow_errors(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    exception: MusicAssistantClientException,
    error_reason: str,
) -> None:
    """Test hassio discovery flow with connection errors."""
    mock_get_server_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_HASSIO},
        data=HASSIO_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error_reason


async def test_zeroconf_addon_server_ignored(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf discovery ignores servers running as add-on."""
    addon_zeroconf_data = deepcopy(ZEROCONF_DATA)
    addon_zeroconf_data.properties["homeassistant_addon"] = (
        "True"  # Zeroconf properties are strings
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=addon_zeroconf_data,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_discovered_addon"


async def test_zeroconf_old_schema_addon_not_ignored(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf discovery does NOT ignore add-on servers with old schema version."""
    old_schema_addon_data = deepcopy(ZEROCONF_DATA)
    old_schema_version = AUTH_SCHEMA_VERSION - 1
    old_schema_addon_data.properties["schema_version"] = str(old_schema_version)
    old_schema_addon_data.properties["min_supported_schema_version"] = str(
        old_schema_version
    )
    old_schema_addon_data.properties["homeassistant_addon"] = (
        "True"  # Zeroconf properties are strings
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=old_schema_addon_data,
    )
    await hass.async_block_till_done()

    # Should proceed to discovery_confirm, not abort
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_user_flow_with_auth_required(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test user flow with schema >= 28 redirects to auth."""
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
    # Should fall back to manual auth (no request context in tests)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_manual"


async def test_zeroconf_flow_with_auth_required(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf flow with schema >= 28 redirects to auth after confirmation."""
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
    # Should fall back to manual auth (no request context in tests)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_manual"


async def test_hassio_flow_with_token(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test hassio discovery flow with token provided."""
    # Add token to hassio discovery data
    hassio_data_with_token = HassioServiceInfo(
        config={
            "host": "addon-music-assistant",
            "port": 8094,
            "auth_token": "test_token",
        },
        name="Music Assistant",
        slug="music_assistant",
        uuid="1234",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_HASSIO},
        data=hassio_data_with_token,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_URL: "http://addon-music-assistant:8094",
        CONF_TOKEN: "test_token",
    }
    assert result["result"].unique_id == "1234"


async def test_auth_flow_success(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test successful authentication flow."""
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_manual"

    with patch("homeassistant.components.music_assistant.config_flow._test_connection"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "test_auth_token"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_URL: "http://localhost:8095",
        CONF_TOKEN: "test_auth_token",
    }
    assert result["result"].unique_id == "1234"


async def test_finish_auth_token_exchange(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test that finish_auth exchanges short-lived token for long-lived token."""
    # Create flow instance
    flow = MusicAssistantConfigFlow()
    flow.hass = hass
    flow.url = "http://localhost:8095"
    flow.token = "short_lived_session_token"
    flow.server_info = mock_get_server_info.return_value

    # Mock the token exchange
    with patch(
        "homeassistant.components.music_assistant.config_flow.create_long_lived_token",
        return_value="long_lived_token_12345",
    ) as mock_create_token:
        # Call async_step_finish_auth to test token exchange
        result = await flow.async_step_finish_auth()

    # Verify token was exchanged
    mock_create_token.assert_called_once()
    call_args = mock_create_token.call_args
    assert call_args[0][0] == "http://localhost:8095"
    assert call_args[0][1] == "short_lived_session_token"
    assert call_args[0][2] == "Home Assistant"
    assert call_args[1]["aiohttp_session"] is not None

    # Verify entry was created with long-lived token
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_URL: "http://localhost:8095",
        CONF_TOKEN: "long_lived_token_12345",
    }


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow shows confirmation before auth."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["url"] == "http://localhost:8095"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_manual"


async def test_reauth_with_manual_token(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with manual token entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.music_assistant.config_flow._test_connection"
    ) as mock_test_connection:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
            data=mock_config_entry.data,
        )
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        assert result["step_id"] == "auth_manual"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "new_valid_token"},
        )

        mock_test_connection.assert_called_once_with(
            hass, "http://localhost:8095", "new_valid_token"
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert mock_config_entry.data[CONF_TOKEN] == "new_valid_token"


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (AuthenticationFailed("auth_failed"), "auth_failed"),
        (InvalidToken("invalid_token"), "auth_failed"),
    ],
)
async def test_auth_manual_invalid_token(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    exception: Exception,
    error_key: str,
) -> None:
    """Test manual auth with invalid token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://localhost:8095"},
    )
    assert result["step_id"] == "auth_manual"

    with patch(
        "homeassistant.components.music_assistant.config_flow._test_connection",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "invalid_token"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_manual"
    assert result["errors"] == {"base": error_key}


@pytest.mark.parametrize(
    ("exception", "abort_reason"),
    [
        (CannotConnect("cannot_connect"), "cannot_connect"),
        (InvalidServerVersion("invalid_server_version"), "invalid_server_version"),
        (MusicAssistantClientException("unknown"), "unknown"),
    ],
)
async def test_auth_manual_connection_errors(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    exception: Exception,
    abort_reason: str,
) -> None:
    """Test manual auth with connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://localhost:8095"},
    )
    assert result["step_id"] == "auth_manual"

    with patch(
        "homeassistant.components.music_assistant.config_flow._test_connection",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TOKEN: "test_token"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason


async def test_finish_auth_reauth_source(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test finish_auth updates entry when source is reauth."""
    mock_config_entry.add_to_hass(hass)

    flow = MusicAssistantConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id}
    flow.url = "http://localhost:8095"
    flow.token = "session_token"

    with patch(
        "homeassistant.components.music_assistant.config_flow.create_long_lived_token",
        return_value="new_long_lived_token",
    ):
        result = await flow.async_step_finish_auth()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "new_long_lived_token"


@pytest.mark.parametrize(
    ("exception", "abort_reason"),
    [
        (TimeoutError(), "cannot_connect"),
        (CannotConnect("cannot_connect"), "cannot_connect"),
        (AuthenticationFailed("auth_failed"), "auth_failed"),
        (InvalidToken("invalid_token"), "auth_failed"),
        (InvalidServerVersion("invalid_version"), "invalid_server_version"),
        (MusicAssistantClientException("unknown"), "unknown"),
    ],
)
async def test_finish_auth_errors(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    exception: Exception,
    abort_reason: str,
) -> None:
    """Test finish_auth handles errors during token exchange."""
    flow = MusicAssistantConfigFlow()
    flow.hass = hass
    flow.url = "http://localhost:8095"
    flow.token = "session_token"

    with patch(
        "homeassistant.components.music_assistant.config_flow.create_long_lived_token",
        side_effect=exception,
    ):
        result = await flow.async_step_finish_auth()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason


async def test_auth_step_with_oauth2_callback(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test auth step receiving OAuth2 callback with code parameter."""
    flow = MusicAssistantConfigFlow()
    flow.hass = hass
    flow.url = "http://localhost:8095"
    flow.server_info = mock_get_server_info.return_value

    result = await flow.async_step_auth(user_input={"code": "test_session_token"})

    assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
    assert result["step_id"] == "finish_auth"
    assert flow.token == "test_session_token"


async def test_auth_step_with_error(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test auth step receiving error from OAuth2 callback."""
    flow = MusicAssistantConfigFlow()
    flow.hass = hass
    flow.url = "http://localhost:8095"
    flow.server_info = mock_get_server_info.return_value

    result = await flow.async_step_auth(user_input={"error": "access_denied"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_error"


async def test_get_server_info_helper(
    hass: HomeAssistant,
) -> None:
    """Test _get_server_info helper function."""
    expected_server_info = ServerInfoMessage.from_json(
        await async_load_fixture(hass, "server_info_message.json", DOMAIN)
    )

    with patch(
        "homeassistant.components.music_assistant.config_flow.get_server_info"
    ) as mock_lib_get_server_info:
        mock_lib_get_server_info.return_value = expected_server_info

        result = await _get_server_info(hass, "http://localhost:8095")

        assert result == expected_server_info
        mock_lib_get_server_info.assert_called_once()


async def test_test_connection_helper(
    hass: HomeAssistant,
) -> None:
    """Test _test_connection helper function."""
    with patch(
        "homeassistant.components.music_assistant.config_flow.MusicAssistantClient"
    ) as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance

        await _test_connection(hass, "http://localhost:8095", "test_token")

        mock_instance.send_command.assert_called_once_with("info")


async def test_auth_with_redirect_uri(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test auth step with redirect URI available."""
    flow = MusicAssistantConfigFlow()
    flow.hass = hass
    flow.url = "http://localhost:8095"
    flow.flow_id = "test_flow_id"
    flow.server_info = mock_get_server_info.return_value

    with (
        patch(
            "homeassistant.components.music_assistant.config_flow.async_get_redirect_uri",
            return_value="http://localhost:8123/auth/external/callback",
        ),
        patch(
            "homeassistant.components.music_assistant.config_flow._encode_jwt",
            return_value="test_jwt_state",
        ),
    ):
        result = await flow.async_step_auth()

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"
    assert "http://localhost:8095/login" in result["url"]
    assert (
        "return_url=http%3A%2F%2Flocalhost%3A8123%2Fauth%2Fexternal%2Fcallback%3Fstate%3Dtest_jwt_state"
        in result["url"]
    )
    assert "device_name=Home+Assistant" in result["url"]
