"""Tests for Google Mail."""
import http
import time
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
from google.auth.exceptions import RefreshError
import pytest
from voluptuous.error import Invalid

from homeassistant import config_entries
from homeassistant.components.google_mail import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import SENSOR, ComponentSetup

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


async def test_set_vacation(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test service call set vacation."""
    await setup_integration()

    with patch("homeassistant.components.google_mail.build") as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "set_vacation",
            {
                "entity_id": SENSOR,
                "enabled": True,
                "title": "Vacation",
                "message": "Vacation message",
                "plain_text": False,
                "restrict_contacts": True,
                "restrict_domain": True,
                "start": "2022-11-20",
                "end": "2022-11-26",
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 5

    with patch("homeassistant.components.google_mail.build") as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "set_vacation",
            {
                "entity_id": SENSOR,
                "enabled": True,
                "title": "Vacation",
                "message": "Vacation message",
                "plain_text": True,
                "restrict_contacts": True,
                "restrict_domain": True,
                "start": "2022-11-20",
                "end": "2022-11-26",
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 5


async def test_email(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test service call draft email."""
    await setup_integration()

    with patch("homeassistant.components.google_mail.build") as mock_client:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "example_gmail_com",
            {
                "title": "Test",
                "message": "test email",
                "target": "text@example.com",
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 5

    with patch("homeassistant.components.google_mail.build") as mock_client:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "example_gmail_com",
            {
                "title": "Test",
                "message": "test email",
                "target": "text@example.com",
                "data": {"send": False},
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 5


async def test_email_voluptuous_error(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test voluptuous error thrown when drafting email."""
    await setup_integration()

    with pytest.raises(Invalid) as ex:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "example_gmail_com",
            {
                "title": "Test",
                "message": "test email",
            },
            blocking=True,
        )
    assert ex.match("recipient address required")

    with pytest.raises(Invalid) as ex:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "example_gmail_com",
            {
                "title": "Test",
            },
            blocking=True,
        )
    assert ex.getrepr("required key not provided")


async def test_reauth_trigger(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test reauth is triggered after a refresh error during service call."""
    await setup_integration()

    with patch(
        "googleapiclient.http.HttpRequest.execute", side_effect=RefreshError
    ), pytest.raises(RefreshError):
        await hass.services.async_call(
            DOMAIN,
            "set_vacation",
            {
                "entity_id": SENSOR,
                "enabled": True,
                "title": "Vacation",
                "message": "Vacation message",
                "plain_text": True,
                "restrict_contacts": True,
                "restrict_domain": True,
                "start": "2022-11-20",
                "end": "2022-11-26",
            },
            blocking=True,
        )

    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
