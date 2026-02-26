"""Tests for the Xbox integration."""

from datetime import timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from httpx import ConnectTimeout, HTTPStatusError, ProtocolError, RequestError, Response
import pytest
from pythonxbox.api.provider.smartglass.models import SmartglassConsoleList
from pythonxbox.common.exceptions import AuthenticationException
import respx

from homeassistant.components.xbox.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)


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
        ("people", "get_friends_by_xuid"),
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
) -> None:
    """Test adding of new and removal of stale devices at runtime."""

    xbox_live_client.smartglass.get_console_list.return_value = SmartglassConsoleList(
        **await async_load_json_object_fixture(
            hass, "smartglass_console_list_empty.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert device_registry.async_get_device({(DOMAIN, "ABCDEFG")}) is None
    assert device_registry.async_get_device({(DOMAIN, "HIJKLMN")}) is None

    xbox_live_client.smartglass.get_console_list.return_value = SmartglassConsoleList(
        **await async_load_json_object_fixture(
            hass, "smartglass_console_list.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, "ABCDEFG")})
    assert device_registry.async_get_device({(DOMAIN, "HIJKLMN")})

    xbox_live_client.smartglass.get_console_list.return_value = SmartglassConsoleList(
        **await async_load_json_object_fixture(
            hass, "smartglass_console_list_empty.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, "ABCDEFG")}) is None
    assert device_registry.async_get_device({(DOMAIN, "HIJKLMN")}) is None
