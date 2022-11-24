"""Tests for Google Mail."""
import http
import time
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
import pytest

from homeassistant.components.google_mail import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_success(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test successful setup and unload."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert entries[0].state is ConfigEntryState.NOT_LOADED
    assert not len(hass.services.async_services().get(DOMAIN, {}))


@pytest.mark.parametrize(
    "scopes",
    [
        [],
        [
            "https://www.googleapis.com/auth/gmail.settings.basic+plus+extra"
        ],  # Required scope is a prefix
        ["https://www.googleapis.com/auth/gmail.settings.basic"],
    ],
    ids=["no_scope", "required_scope_prefix", "other_scope"],
)
async def test_missing_required_scopes_requires_reauth(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test that reauth is invoked when required scopes are not present."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test expired token is refreshed."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
        },
    )

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data["token"]["access_token"] == "updated-access-token"
    assert entries[0].data["token"]["expires_in"] == 3600


@pytest.mark.parametrize(
    "expires_at,status,expected_state",
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["failure_requires_reauth", "transient_failure"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        status=status,
    )

    await setup_integration()

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is expected_state


async def test_expired_token_refresh_client_error(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test failure while refreshing token with a client error."""

    with patch(
        "homeassistant.components.google_mail.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientError,
    ):
        await setup_integration()

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is ConfigEntryState.SETUP_RETRY
