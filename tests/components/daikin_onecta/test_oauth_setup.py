"""Tests for OAuth2 setup error handling (HA 2026.3+)."""
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import RequestInfo
import pytest
from yarl import URL

from homeassistant.components.daikin_onecta import async_setup_entry
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
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
async def test_setup_entry_reauth_on_token_request(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Token reauth errors during ensure must raise ConfigEntryAuthFailed."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            side_effect=_reauth_error(),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await async_setup_entry(hass, config_entry)


@pytest.mark.asyncio
async def test_setup_entry_not_ready_on_transient_token_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Recoverable OAuth token errors must raise ConfigEntryNotReady."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            side_effect=_token_error(),
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, config_entry)


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
        pytest.raises(ConfigEntryNotReady) as exc_info,
    ):
        await async_setup_entry(hass, config_entry)

    if exc_info.value.translation_domain != DOMAIN:
        pytest.fail(f"unexpected translation_domain: {exc_info.value.translation_domain}")
    if exc_info.value.translation_key != "oauth2_implementation_unavailable":
        pytest.fail(f"unexpected translation_key: {exc_info.value.translation_key}")


@pytest.mark.asyncio
async def test_setup_entry_preserves_reauth_from_first_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """First refresh reauth must not be converted into ConfigEntryNotReady."""
    # A broad Exception handler around async_config_entry_first_refresh would
    # swallow ConfigEntryAuthFailed and prevent the reauth UI from starting.
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            new=AsyncMock(return_value="token"),
        ),
        patch.object(
            OnectaDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            side_effect=ConfigEntryAuthFailed("token expired"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await async_setup_entry(hass, config_entry)

    if config_entry.state is ConfigEntryState.LOADED:
        pytest.fail("config entry should not be LOADED after reauth failure")
