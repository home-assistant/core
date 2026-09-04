"""Tests for the Xbox integration."""

from datetime import timedelta
from http import HTTPStatus
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from httpx import ConnectTimeout, HTTPStatusError, ProtocolError, RequestError, Response
import pytest
from pythonxbox.api.provider.smartglass.models import SmartglassConsoleList
from pythonxbox.common.exceptions import AuthenticationException
import respx

from homeassistant.components.xbox.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("xbox_live_client")
async def test_entry_setup_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [
        ConnectTimeout(""),
        HTTPStatusError("", request=Mock(), response=Mock()),
        ProtocolError(""),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test config entry not ready."""

    xbox_live_client.smartglass.get_console_list.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("xbox_live_client")
async def test_config_implementation_not_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test implementation not available."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.xbox.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("state", "exception"),
    [
        (
            ConfigEntryState.SETUP_ERROR,
            OAuth2TokenRequestReauthError(domain=DOMAIN, request_info=Mock()),
        ),
        (
            ConfigEntryState.SETUP_RETRY,
            OAuth2TokenRequestTransientError(domain=DOMAIN, request_info=Mock()),
        ),
        (
            ConfigEntryState.SETUP_RETRY,
            ClientError,
        ),
    ],
)
@respx.mock
async def test_oauth_session_refresh_failure_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    state: ConfigEntryState,
    exception: Exception | type[Exception],
    oauth2_session: AsyncMock,
) -> None:
    """Test OAuth2 session refresh failures."""

    oauth2_session.async_ensure_token_valid.side_effect = exception
    oauth2_session.valid_token = False

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state


@pytest.mark.parametrize(
    ("state", "exception"),
    [
        (
            ConfigEntryState.SETUP_RETRY,
            HTTPStatusError(
                "", request=MagicMock(), response=Response(HTTPStatus.IM_A_TEAPOT)
            ),
        ),
        (ConfigEntryState.SETUP_RETRY, RequestError("", request=Mock())),
        (ConfigEntryState.SETUP_ERROR, AuthenticationException),
    ],
)
@respx.mock
async def test_oauth_session_refresh_user_and_xsts_token_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    state: ConfigEntryState,
    exception: Exception | type[Exception],
    oauth2_session: AsyncMock,
) -> None:
    """Test OAuth2 user and XSTS token refresh failures."""
    oauth2_session.valid_token = True

    respx.post(OAUTH2_TOKEN).mock(side_effect=exception)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state


@pytest.mark.parametrize(
    "exception",
    [
        ConnectTimeout(""),
        HTTPStatusError("", request=Mock(), response=Mock()),
        ProtocolError(""),
    ],
)
@pytest.mark.parametrize(
    ("provider", "method"),
    [
        ("smartglass", "get_console_status"),
        ("catalog", "get_product_from_alternate_id"),
        ("people", "get_friend_by_xuid"),
        ("people", "get_friends_own"),
    ],
)
async def test_coordinator_update_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    exception: Exception,
    provider: str,
    method: str,
) -> None:
    """Test coordinator update failed."""

    provider = getattr(xbox_live_client, provider)
    getattr(provider, method).side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.freeze_time
async def test_dynamic_devices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test adding of new and removal of stale devices at runtime."""
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    xbox_live_client.smartglass.get_console_list.return_value = SmartglassConsoleList(
        **await async_load_json_object_fixture(
            hass, "smartglass_console_list_empty.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "ABCDEFG"), config_entry.entry_id
        )
        is None
    )

    xbox_live_client.smartglass.get_console_list.return_value = SmartglassConsoleList(
        **await async_load_json_object_fixture(
            hass, "smartglass_console_list.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device := device_registry.async_get_device_by_identifier(
            (DOMAIN, "ABCDEFG"), config_entry.entry_id
        )
    )

    response = await client.remove_device(device.id)
    assert not response["success"]

    xbox_live_client.smartglass.get_console_list.return_value = SmartglassConsoleList(
        **await async_load_json_object_fixture(
            hass, "smartglass_console_list_empty.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    response = await client.remove_device(device.id)
    assert response["success"]

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "ABCDEFG"), config_entry.entry_id
        )
        is None
    )

    # Test that service devices cannot be removed
    assert (
        account := device_registry.async_get_device_by_identifier(
            (DOMAIN, "271958441785640"), config_entry.entry_id
        )
    )
    response = await client.remove_device(account.id)
    assert not response["success"]


@pytest.mark.usefixtures("xbox_live_client")
async def test_no_reload_on_token_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the entry is not reloaded when only the OAuth token is rewritten."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                "token": {**config_entry.data["token"], "access_token": "refreshed"},
            },
        )
        await hass.async_block_till_done()

    mock_reload.assert_not_called()


@pytest.mark.usefixtures("xbox_live_client")
async def test_reload_on_auth_implementation_change(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the entry is reloaded when reauth selects a different implementation.

    OAuth2Session caches the implementation it was constructed with and never
    re-reads it, so a reauth that switches auth_implementation needs a reload
    even though it isn't a subentry change.
    """

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, "auth_implementation": "other"},
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(config_entry.entry_id)


async def test_reload_on_token_change_after_auth_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entry is reloaded when reauth replaces the token.

    A coordinator stops scheduling updates once it has failed to
    authenticate, so a token-only write, which is ignored while everything is
    updating successfully, has to reload the entry instead. Without it nothing
    would ever poll again with the token reauth just wrote.
    """

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert not config_entry.runtime_data.has_auth_failure()

    xbox_live_client.smartglass.get_console_status.side_effect = ConfigEntryAuthFailed
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert config_entry.runtime_data.has_auth_failure()

    xbox_live_client.smartglass.get_console_status.side_effect = None

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                "token": {**config_entry.data["token"], "access_token": "reauthed"},
            },
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(config_entry.entry_id)


async def test_no_reload_on_token_change_after_transient_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entry is not reloaded when a token is written after a timeout.

    A coordinator keeps scheduling updates after a transient failure, so it
    recovers on its own and a reload would only interrupt it.
    """

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    xbox_live_client.smartglass.get_console_status.side_effect = ConnectTimeout(
        "timeout"
    )
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not config_entry.runtime_data.status.last_update_success
    assert not config_entry.runtime_data.has_auth_failure()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                "token": {**config_entry.data["token"], "access_token": "refreshed"},
            },
        )
        await hass.async_block_till_done()

    mock_reload.assert_not_called()


@pytest.mark.usefixtures("xbox_live_client")
async def test_reload_on_subentry_added(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the entry is reloaded when a friend subentry is added."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_add_subentry(
            config_entry,
            ConfigSubentry(
                data=MappingProxyType({}),
                subentry_type="friend",
                title="new_friend",
                unique_id="2533274838782905",
            ),
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(config_entry.entry_id)


@pytest.mark.usefixtures("xbox_live_client")
async def test_reload_on_subentry_removed(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the entry is reloaded when a friend subentry is removed."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    subentry_id = next(iter(config_entry.subentries))

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_remove_subentry(config_entry, subentry_id)
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(config_entry.entry_id)


@pytest.mark.usefixtures("xbox_live_client")
async def test_reload_on_subentry_rename(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the entry is reloaded when a friend subentry is renamed.

    ConfigSubentry instances are mutated in place, so this only works if the
    integration snapshots its subentries by value.
    """

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    subentry = next(iter(config_entry.subentries.values()))

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_subentry(
            config_entry, subentry, title="renamed_friend"
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(config_entry.entry_id)


@pytest.mark.usefixtures("xbox_live_client")
async def test_reload_on_subentry_data_change(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the entry is reloaded when a subentry's data changes without a title change.

    The snapshot compares the whole subentry (via as_dict()), not just the
    title, so a data-only change must reload too.
    """

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    subentry = next(iter(config_entry.subentries.values()))

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_subentry(
            config_entry, subentry, data={"favorite": True}
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(config_entry.entry_id)


@pytest.mark.usefixtures("xbox_live_client")
async def test_no_reload_on_entry_title_change(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the entry is not reloaded when only the entry's own title changes."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(config_entry, title="Renamed Entry")
        await hass.async_block_till_done()

    mock_reload.assert_not_called()


@pytest.mark.usefixtures("xbox_live_client")
async def test_no_reload_on_entry_options_change(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the entry is not reloaded when only its options change.

    Options are entry-level, not subentry data, so this must not reload
    either.
    """

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(config_entry, options={"foo": "bar"})
        await hass.async_block_till_done()

    mock_reload.assert_not_called()
