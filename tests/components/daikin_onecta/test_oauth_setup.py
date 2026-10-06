"""Tests for OAuth2 setup error handling (HA 2026.3+)."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import RequestInfo
import pytest
from yarl import URL

from homeassistant.components.daikin_onecta import _async_update_listener
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import MockConfigEntry


def _token_request_info() -> RequestInfo:
    url = URL("https://idp.onecta.daikineurope.com/v1/oidc/token")
    return RequestInfo(url=url, method="POST", headers={}, real_url=url)


def _reauth_error() -> OAuth2TokenRequestReauthError:
    return OAuth2TokenRequestReauthError(
        domain=DOMAIN,
        request_info=_token_request_info(),
        status=401,
        message="invalid_grant",
    )


def _token_error() -> OAuth2TokenRequestError:
    return OAuth2TokenRequestError(
        domain=DOMAIN,
        request_info=_token_request_info(),
        status=500,
        message="server error",
    )


@pytest.mark.asyncio
async def test_setup_entry_rejected_token_requires_authentication(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Rejected OAuth tokens require authentication, not a setup retry."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            side_effect=_reauth_error(),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_retries_token_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Transient OAuth token errors retry setup."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            side_effect=_token_error(),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_retries_token_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Token validation timeouts preserve a translated retry reason."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            side_effect=TimeoutError,
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.reason == "oauth2_token_request_failed"


@pytest.mark.asyncio
async def test_setup_entry_not_ready_when_implementation_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Missing OAuth implementation must raise ConfigEntryNotReady."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            side_effect=ImplementationUnavailableError("no impl"),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_listener_notifies_entities_without_cloud_refresh() -> None:
    """Presentation-only option changes must not consume cloud quota."""
    coordinator = MagicMock()
    coordinator.update_settings.return_value = True
    coordinator.async_request_refresh = AsyncMock()
    config_entry = MagicMock(runtime_data=coordinator)

    await _async_update_listener(MagicMock(), config_entry)

    coordinator.update_settings.assert_called_once_with(config_entry)
    coordinator.async_request_refresh.assert_not_awaited()
    coordinator.async_update_listeners.assert_called_once_with()


async def test_update_listener_ignores_oauth_token_renewal() -> None:
    """OAuth token renewal must not trigger a cloud refresh."""
    coordinator = MagicMock()
    coordinator.update_settings.return_value = False
    coordinator.async_request_refresh = AsyncMock()
    config_entry = MagicMock(runtime_data=coordinator)

    await _async_update_listener(MagicMock(), config_entry)

    coordinator.update_settings.assert_called_once_with(config_entry)
    coordinator.async_request_refresh.assert_not_awaited()
    coordinator.async_update_listeners.assert_not_called()
