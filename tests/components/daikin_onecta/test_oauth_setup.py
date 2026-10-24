"""Tests for OAuth2 setup error handling (HA 2026.3+)."""

from unittest.mock import MagicMock, patch

from aiohttp import RequestInfo
from daikin_onecta import OnectaAuthenticationError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from yarl import URL

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .test_climate_snapshots import _async_setup_fixture


@pytest.mark.parametrize("status", [401, 403])
async def test_setup_rejected_cloud_token_requires_authentication(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    status: int,
) -> None:
    """Classify rejected API tokens as authentication failures, not retries."""
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator.async_get_access_token",
            return_value="token",
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator._async_get_cloud_devices",
            side_effect=OnectaAuthenticationError(
                status=status, method="GET", path="/v1/gateway-devices"
            ),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize("status", [401, 403])
async def test_poll_rejected_cloud_token_stops_polling_without_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    status: int,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Report authentication failure without adding a reauthentication flow."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    with patch(
        "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator._async_get_cloud_devices",
        side_effect=OnectaAuthenticationError(
            status=status, method="GET", path="/v1/gateway-devices"
        ),
    ):
        assert coordinator.update_interval is not None
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert coordinator.last_exception.translation_key == "authentication_failed"
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert config_entry.state is ConfigEntryState.LOADED


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
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator.async_get_access_token",
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
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator.async_get_access_token",
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
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator.async_get_access_token",
            side_effect=TimeoutError("timeout"),
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.reason in {
        "oauth2_token_request_failed",
        "Unable to obtain Daikin OAuth token: timeout",
    }


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
