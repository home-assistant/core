"""Tests for Google Mail."""

import http
import time
from unittest.mock import Mock, patch

from aiohttp.client_exceptions import ClientError
import pytest

from homeassistant.components.google_mail import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import device_registry as dr

from .conftest import GOOGLE_TOKEN_URI, ComponentSetup

from tests.test_util.aiohttp import AiohttpClientMocker

REAUTH_ISSUE_TRANSLATIONS = [
    "component.homeassistant.issues.config_entry_reauth.title",
    "component.homeassistant.issues.config_entry_reauth.description",
]


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


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test expired token is refreshed."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
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
    ("expires_at", "status", "expected_state", "ignore_missing_translations"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
            REAUTH_ISSUE_TRANSLATIONS,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
            [],
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.BAD_REQUEST,
            ConfigEntryState.SETUP_ERROR,
            REAUTH_ISSUE_TRANSLATIONS,
        ),
    ],
    ids=["failure_requires_reauth", "transient_failure", "revoked_auth"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
    ignore_missing_translations: list[str],
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
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


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [REAUTH_ISSUE_TRANSLATIONS],
)
async def test_token_refresh_reauth_error_during_setup(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test setup starts reauth for OAuth reauth errors."""
    with patch(
        "homeassistant.components.google_mail.OAuth2Session.async_ensure_token_valid",
        side_effect=OAuth2TokenRequestReauthError(
            request_info=Mock(),
            domain=DOMAIN,
        ),
    ):
        await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == SOURCE_REAUTH


async def test_token_refresh_transient_error_during_setup(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test setup retries for transient OAuth token refresh errors."""
    with patch(
        "homeassistant.components.google_mail.OAuth2Session.async_ensure_token_valid",
        side_effect=OAuth2TokenRequestTransientError(
            request_info=Mock(),
            domain=DOMAIN,
        ),
    ):
        await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_integration: ComponentSetup,
) -> None:
    """Test device info."""
    await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})

    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == "Google, Inc."
    assert device.name == "example@gmail.com"
