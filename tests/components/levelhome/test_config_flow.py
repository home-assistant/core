"""Tests for the Level Lock config flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.levelhome.config_flow import OAuth2FlowHandler
from homeassistant.components.levelhome.const import (
    CONF_CONTACT_INFO,
    CONF_PARTNER_BASE_URL,
    DEFAULT_PARTNER_BASE_URL,
    DEVICE_CODE_INITIATE_PATH,
    DEVICE_CODE_POLL_PATH,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


def _get_fake_impl() -> SimpleNamespace:
    """Get a fake OAuth2 implementation."""
    return SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="test-client-id",
    )


@pytest.fixture(name="mock_impl")
def mock_impl_fixture() -> SimpleNamespace:
    """Return a fake OAuth2 implementation."""
    return _get_fake_impl()


@pytest.fixture(name="mock_implementations")
def mock_implementations_fixture(mock_impl: SimpleNamespace):
    """Patch async_get_implementations to return our fake implementation."""
    with patch(
        "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
        return_value={"impl": mock_impl},
    ) as mock:
        yield mock


@pytest.mark.usefixtures("recorder_mock")
async def test_user_step_shows_form(
    hass: HomeAssistant,
    mock_implementations: None,
) -> None:
    """Test user step shows form when no input provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.usefixtures("recorder_mock")
async def test_user_step_missing_configuration(hass: HomeAssistant) -> None:
    """Test abort with missing_configuration when no implementation and no app creds."""
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_application_credentials",
            return_value={},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "missing_configuration"


@pytest.mark.usefixtures("recorder_mock")
async def test_user_step_missing_credentials(hass: HomeAssistant) -> None:
    """Test abort with missing_credentials when app creds exist but no impl."""
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_application_credentials",
            return_value={DOMAIN: object()},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("recorder_mock")
async def test_user_step_email_contact(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test user step with email contact type."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 5},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "verify"


@pytest.mark.usefixtures("recorder_mock")
async def test_user_step_phone_contact(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test user step with phone contact type."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 5},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "+11234567890"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "verify"


@pytest.mark.usefixtures("recorder_mock")
async def test_user_step_duplicate_entry(
    hass: HomeAssistant,
    mock_implementations: None,
) -> None:
    """Test abort when entry already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={"auth_implementation": DOMAIN},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("recorder_mock")
async def test_user_step_reauth_wrong_account(
    hass: HomeAssistant,
    mock_implementations: None,
) -> None:
    """Test abort when reauth with different account."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="old@example.com",
        data={"auth_implementation": DOMAIN},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "new@example.com"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


@pytest.mark.usefixtures("recorder_mock")
async def test_initiate_step_missing_configuration(hass: HomeAssistant) -> None:
    """Test abort in initiate step with missing_configuration."""
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": _get_fake_impl()},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_application_credentials",
            return_value={},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "missing_configuration"


@pytest.mark.usefixtures("recorder_mock")
async def test_initiate_step_missing_credentials(hass: HomeAssistant) -> None:
    """Test abort in initiate step with missing_credentials."""
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": _get_fake_impl()},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_application_credentials",
            return_value={DOMAIN: object()},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("recorder_mock")
async def test_initiate_step_http_error(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test abort when device code initiation returns HTTP error."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        status=400,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_failed"


@pytest.mark.usefixtures("recorder_mock")
async def test_initiate_step_client_error(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test abort when device code initiation raises ClientError."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        exc=ClientError(),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_failed"


@pytest.mark.usefixtures("recorder_mock")
async def test_initiate_step_missing_device_code(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test abort when response missing device_code."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"user_code": "USER123", "interval": 5},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("recorder_mock")
async def test_initiate_step_missing_user_code(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test abort when response missing user_code."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "interval": 5},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("recorder_mock")
async def test_initiate_step_sms_delivery(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test initiate step with SMS delivery method for phone numbers."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 5},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "1234567890"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "verify"


@pytest.mark.usefixtures("recorder_mock")
async def test_verify_step_shows_form(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test verify step displays user code."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 5},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "verify"
    assert result["description_placeholders"]["user_code"] == "USER123"


async def test_verify_step_missing_user_code(hass: HomeAssistant) -> None:
    """Test abort in verify step when user_code is missing."""
    handler = OAuth2FlowHandler()
    handler.hass = hass
    handler._user_code = None

    result = await handler.async_step_verify(None)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("recorder_mock")
async def test_poll_step_success(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test successful polling for token."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 0},
    )
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_POLL_PATH}",
        json={
            "access_token": "at-123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "rt-123",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Level Lock"
    assert result["data"]["token"]["access_token"] == "at-123"
    assert result["options"][CONF_PARTNER_BASE_URL] == DEFAULT_PARTNER_BASE_URL


@pytest.mark.usefixtures("recorder_mock")
async def test_poll_step_success_defaults(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test successful polling with default token values."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 0},
    )
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_POLL_PATH}",
        json={"access_token": "at-123"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    token = result["data"]["token"]
    assert token["token_type"] == "Bearer"
    assert token["expires_in"] == 3600


@pytest.mark.usefixtures("recorder_mock")
async def test_poll_step_authorization_pending(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test polling continues on authorization_pending."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 0},
    )

    responses = [
        {"error": "authorization_pending"},
        {
            "access_token": "at-123",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    ]
    call_count = 0

    async def poll_side_effect(method, url, data):
        nonlocal call_count
        response = responses[call_count]
        call_count += 1
        return AiohttpClientMockResponse(method, url, json=response)

    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_POLL_PATH}",
        side_effect=poll_side_effect,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("recorder_mock")
async def test_poll_step_expired_token(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test abort when device code expires."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 0},
    )
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_POLL_PATH}",
        json={"error": "expired_token"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_timeout"


@pytest.mark.usefixtures("recorder_mock")
async def test_poll_step_invalid_grant(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test abort when grant is invalid."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 0},
    )
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_POLL_PATH}",
        json={"error": "invalid_grant"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_timeout"


@pytest.mark.usefixtures("recorder_mock")
async def test_poll_step_other_error(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test abort on other errors."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 0},
    )
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_POLL_PATH}",
        json={"error": "access_denied"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_failed"


@pytest.mark.usefixtures("recorder_mock")
async def test_poll_step_client_error(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test abort when polling raises ClientError."""
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 0},
    )
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_POLL_PATH}",
        exc=ClientError(),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_failed"


@pytest.mark.usefixtures("recorder_mock")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth flow shows confirm and returns to user step."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={"auth_implementation": DOMAIN, "token": {}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.usefixtures("recorder_mock")
async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_implementations: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test successful reauth updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={"auth_implementation": DOMAIN, "token": {"access_token": "old"}},
    )
    entry.add_to_hass(hass)

    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_INITIATE_PATH}",
        json={"device_code": "dc-123", "user_code": "USER123", "interval": 0},
    )
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{DEVICE_CODE_POLL_PATH}",
        json={
            "access_token": "new-at",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_CONTACT_INFO: "test@example.com"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("recorder_mock")
async def test_reauth_without_unique_id(
    hass: HomeAssistant,
    mock_implementations: None,
) -> None:
    """Test reauth with entry that has no unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        data={"auth_implementation": DOMAIN, "token": {}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


def test_detect_contact_type_email() -> None:
    """Test _detect_contact_type detects email correctly."""
    handler = OAuth2FlowHandler()

    method, contact = handler._detect_contact_type("test@example.com")
    assert method == "email"
    assert contact == "test@example.com"

    method, contact = handler._detect_contact_type("  User@Domain.ORG  ")
    assert method == "email"
    assert contact == "User@Domain.ORG"


def test_detect_contact_type_phone() -> None:
    """Test _detect_contact_type detects phone correctly."""
    handler = OAuth2FlowHandler()

    method, contact = handler._detect_contact_type("+11234567890")
    assert method == "sms"
    assert contact == "+11234567890"

    method, contact = handler._detect_contact_type("(123) 456-7890")
    assert method == "sms"
    assert contact == "1234567890"

    method, contact = handler._detect_contact_type("123-456-7890")
    assert method == "sms"
    assert contact == "1234567890"


def test_detect_contact_type_invalid_defaults_to_email() -> None:
    """Test _detect_contact_type defaults to email for invalid input."""
    handler = OAuth2FlowHandler()

    method, contact = handler._detect_contact_type("invalid")
    assert method == "email"
    assert contact == "invalid"


def test_build_partner_url() -> None:
    """Test _build_partner_url builds URLs correctly."""
    handler = OAuth2FlowHandler()
    handler._partner_base_url = "https://example.com"

    url = handler._build_partner_url("/api/test")
    assert url == "https://example.com/api/test"


def test_generate_pkce_pair() -> None:
    """Test _generate_pkce_pair generates valid PKCE pair."""
    handler = OAuth2FlowHandler()

    verifier, challenge = handler._generate_pkce_pair()
    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert verifier != challenge


def test_extra_authorize_data() -> None:
    """Test extra_authorize_data property returns expected scope."""
    handler = OAuth2FlowHandler()
    assert handler.extra_authorize_data == {"scope": "all"}


def test_logger_property() -> None:
    """Test logger property returns logger."""
    handler = OAuth2FlowHandler()
    logger = handler.logger
    assert logger.name == "homeassistant.components.levelhome.config_flow"
