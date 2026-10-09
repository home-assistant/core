"""Define tests for the Music Assistant Integration config flow."""

import asyncio
from collections.abc import Generator
from copy import deepcopy
from ipaddress import ip_address
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import Discovery
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
    CONF_USE_APP,
    MusicAssistantConfigFlow,
    _get_server_info,
    _test_connection,
)
from homeassistant.components.music_assistant.const import (
    APP_SLUG,
    AUTH_SCHEMA_VERSION,
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
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.network import NoURLAvailableError
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
    assert result["step_id"] == "manual"

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
    assert result["step_id"] == "manual"

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
    assert result["step_id"] == "manual"

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
    assert result["step_id"] == "manual"

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
    assert result["step_id"] == "manual"

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
    ("entry_state", "reload_expected"),
    [
        (ConfigEntryState.SETUP_RETRY, True),
        (ConfigEntryState.LOADED, False),
        (ConfigEntryState.NOT_LOADED, False),
    ],
)
async def test_hassio_flow_unchanged_entry_reloads_only_when_retrying(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    entry_state: ConfigEntryState,
    reload_expected: bool,
) -> None:
    """Test hassio discovery with unchanged data reloads only a retrying entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Assistant",
        data={CONF_URL: "http://addon-music-assistant:8094", CONF_TOKEN: "test_token"},
        unique_id="1234",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, entry_state)

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
    if reload_expected:
        mock_schedule_reload.assert_called_once_with(entry.entry_id)
    else:
        mock_schedule_reload.assert_not_called()


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


@pytest.mark.parametrize(
    ("entry_state", "reload_expected"),
    [
        (ConfigEntryState.SETUP_RETRY, True),
        (ConfigEntryState.LOADED, False),
    ],
)
async def test_zeroconf_addon_server_reloads_retrying_entry(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entry_state: ConfigEntryState,
    reload_expected: bool,
) -> None:
    """Test zeroconf discovery of an add-on server reloads a retrying entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, entry_state)
    addon_zeroconf_data = deepcopy(ZEROCONF_DATA)
    addon_zeroconf_data.properties["homeassistant_addon"] = (
        "True"  # Zeroconf properties are strings
    )

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=addon_zeroconf_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # The add-on entry keeps its own URL, not the zeroconf base_url
    assert mock_config_entry.data == {CONF_URL: "http://localhost:8095"}
    mock_get_server_info.assert_not_called()
    if reload_expected:
        mock_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)
    else:
        mock_schedule_reload.assert_not_called()


async def test_zeroconf_old_schema_addon_not_ignored(
    hass: HomeAssistant,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test zeroconf discovery does NOT ignore old schema add-ons."""
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
    assert result["step_id"] == "manual"

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
    assert result["step_id"] == "manual"

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
    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
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


APP_DISCOVERY_INFO = {
    "host": "addon-music-assistant",
    "port": 8094,
    "auth_token": "test_token",
}
APP_URL = "http://addon-music-assistant:8094"


@pytest.fixture(name="supervisor")
def supervisor_fixture() -> Generator[MagicMock]:
    """Mock running on Supervisor."""
    with patch(
        "homeassistant.components.music_assistant.config_flow.is_hassio",
        return_value=True,
    ) as is_hassio:
        yield is_hassio


@pytest.fixture(name="discovery_info")
def discovery_info_fixture() -> list[Discovery]:
    """Return the app discovery info."""
    return [
        Discovery(
            addon=APP_SLUG,
            service="music_assistant",
            uuid=uuid4(),
            config=APP_DISCOVERY_INFO,
        )
    ]


@pytest.fixture(autouse=True)
def app_wait_time_fixture() -> Generator[None]:
    """Make the app wait loops run without delay."""
    with (
        patch(
            "homeassistant.components.music_assistant.config_flow.APP_START_INTERVAL",
            0,
        ),
        patch(
            "homeassistant.components.music_assistant.config_flow.ONBOARDING_POLL_INTERVAL",
            0,
        ),
    ):
        yield


def _app_server_info(onboard_done: bool) -> ServerInfoMessage:
    """Return server info of the app server."""
    return ServerInfoMessage.from_dict(
        {**SERVER_INFO, "homeassistant_addon": True, "onboard_done": onboard_done}
    )


async def test_on_supervisor_without_app(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test opting out of the app on Supervisor leads to manual setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_app_not_installed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_not_installed: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test installing and starting the app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_app"

    # Make sure the flow continues when the progress task is done.
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert install_addon.call_args == call(APP_SLUG)
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert start_addon.call_args == call(APP_SLUG)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {CONF_URL: APP_URL, CONF_TOKEN: "test_token"}
    assert result["result"].unique_id == "1234"


async def test_app_installed_not_running(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_installed: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test starting an installed app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert install_addon.call_count == 0
    assert start_addon.call_args == call(APP_SLUG)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: APP_URL, CONF_TOKEN: "test_token"}
    assert result["result"].unique_id == "1234"


async def test_app_running(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test using an already running app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert install_addon.call_count == 0
    assert start_addon.call_count == 0
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: APP_URL, CONF_TOKEN: "test_token"}
    assert result["result"].unique_id == "1234"


async def test_app_info_failed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_not_installed: AsyncMock,
    addon_store_info: AsyncMock,
) -> None:
    """Test failing to get the app info."""
    addon_store_info.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_info_failed"


async def test_app_install_failed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_not_installed: AsyncMock,
    install_addon: AsyncMock,
) -> None:
    """Test app install failure."""
    install_addon.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_install_failed"


async def test_app_start_failed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_installed: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test app start failure."""
    start_addon.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_start_failed"


async def test_app_start_timeout(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_installed: AsyncMock,
    start_addon: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test the app server not answering after start."""
    mock_get_server_info.side_effect = CannotConnect("cannot_connect")

    with patch(
        "homeassistant.components.music_assistant.config_flow.APP_START_ROUNDS", 2
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USE_APP: True}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "start_app"

        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_start_failed"
    assert mock_get_server_info.call_count == 2


async def test_app_start_invalid_server_version(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_installed: AsyncMock,
    start_addon: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test a started app running an incompatible server version."""
    mock_get_server_info.side_effect = InvalidServerVersion("invalid_server_version")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_server_version"


async def test_app_discovery_info_failed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test failing to get the app discovery info."""
    get_addon_discovery_info.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_get_discovery_info_failed"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (CannotConnect("cannot_connect"), "cannot_connect"),
        (InvalidServerVersion("invalid_server_version"), "invalid_server_version"),
        (MusicAssistantClientException("unknown"), "unknown"),
    ],
)
async def test_app_running_connect_errors(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test connection errors to a running app."""
    mock_get_server_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_app_already_configured(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test the app server is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_URL: APP_URL, CONF_TOKEN: "test_token"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_app_onboarding(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test the flow waits for the app onboarding to finish."""
    mock_get_server_info.return_value = _app_server_info(onboard_done=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "onboarding"
    assert result["url"] == f"https://example.com/app/{APP_SLUG}"

    # Continuing the flow before onboarding is done keeps waiting
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "onboarding"
    assert result["url"] == f"https://example.com/app/{APP_SLUG}"

    # The poll task resumes the flow once onboarding is done
    mock_get_server_info.return_value = _app_server_info(onboard_done=True)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: APP_URL, CONF_TOKEN: "test_token"}
    assert result["result"].unique_id == "1234"


@pytest.mark.usefixtures("current_request_with_host")
async def test_app_onboarding_flow_removed(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test removing the flow stops polling for onboarding."""
    mock_get_server_info.side_effect = [
        _app_server_info(onboard_done=False),
        _app_server_info(onboard_done=True),
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "onboarding"

    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    assert mock_get_server_info.call_count == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_app_onboarding_flow_removed_during_resume(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test removing the flow while the poll task is resuming it."""
    resume_started = asyncio.Event()
    flow_removed = asyncio.Event()

    async def get_server_info(*args: Any) -> ServerInfoMessage:
        # Calls: 1 finish_app_setup, 2 poll task, 3 the resumed onboarding step
        if mock_get_server_info.call_count == 3:
            resume_started.set()
            await flow_removed.wait()
            return _app_server_info(onboard_done=False)
        return _app_server_info(onboard_done=mock_get_server_info.call_count > 1)

    mock_get_server_info.side_effect = get_server_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await resume_started.wait()
    hass.config_entries.flow.async_abort(result["flow_id"])
    flow_removed.set()
    await hass.async_block_till_done()

    # The removed flow neither raised nor started polling again
    assert mock_get_server_info.call_count == 3


@pytest.mark.usefixtures("current_request_with_host")
async def test_app_onboarding_poll_errors(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test the onboarding poll keeps going over server errors."""
    mock_get_server_info.side_effect = [
        _app_server_info(onboard_done=False),
        CannotConnect("cannot_connect"),
        _app_server_info(onboard_done=True),
        _app_server_info(onboard_done=True),
        _app_server_info(onboard_done=True),
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await hass.async_block_till_done()
    assert mock_get_server_info.call_count == 4

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("current_request_with_host")
async def test_app_onboarding_verify_error(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test polling restarts when verifying the onboarding state fails."""
    mock_get_server_info.side_effect = [
        _app_server_info(onboard_done=False),
        _app_server_info(onboard_done=True),
        CannotConnect("cannot_connect"),
        _app_server_info(onboard_done=True),
        _app_server_info(onboard_done=True),
        _app_server_info(onboard_done=True),
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await hass.async_block_till_done()
    assert mock_get_server_info.call_count == 5

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("current_request_with_host")
async def test_app_onboarding_poll_timeout(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test the onboarding poll stops after its limit without ending the flow."""
    mock_get_server_info.side_effect = [
        _app_server_info(onboard_done=False),
        _app_server_info(onboard_done=False),
        _app_server_info(onboard_done=True),
        _app_server_info(onboard_done=True),
    ]

    with patch(
        "homeassistant.components.music_assistant.config_flow.ONBOARDING_POLL_ROUNDS",
        1,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USE_APP: True}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        await hass.async_block_till_done()
    assert mock_get_server_info.call_count == 2

    # The user coming back to the flow still completes it
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "1234"


async def test_app_onboarding_url_without_request(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test the onboarding URL falls back to the configured Home Assistant URL."""
    await async_process_ha_core_config(hass, {"internal_url": "http://hass.local:8123"})
    mock_get_server_info.return_value = _app_server_info(onboard_done=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USE_APP: True}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == f"http://hass.local:8123/app/{APP_SLUG}"

    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()


async def test_app_onboarding_no_url_available(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
    addon_running: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test the flow aborts when no URL to open the app is available."""
    mock_get_server_info.return_value = _app_server_info(onboard_done=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.music_assistant.config_flow.get_url",
        side_effect=NoURLAvailableError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USE_APP: True}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_url_available"


async def test_hassio_discovery_during_user_flow(
    hass: HomeAssistant,
    supervisor: MagicMock,
    mock_get_server_info: AsyncMock,
) -> None:
    """Test hassio discovery aborts while a user flow is in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "on_supervisor"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=HASSIO_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
