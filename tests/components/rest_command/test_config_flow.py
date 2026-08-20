"""Tests for the RESTful Command config flow."""

import json
from typing import Any

import pytest

from homeassistant.components.rest_command.const import (
    AUTHENTICATION_BEARER,
    AUTHENTICATION_NONE,
    CONF_CONTENT_TYPE,
    CONF_ENDPOINT_NAME,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DEFAULT_PAYLOAD,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_ENDPOINT_NAME: "Primary webhook",
    CONF_URL: "https://example.com/hooks/notify?key=secret",
    CONF_METHOD: "post",
    CONF_AUTHENTICATION: AUTHENTICATION_BEARER,
    CONF_TOKEN: "secret-token",
    CONF_CONTENT_TYPE: "application/json",
    CONF_PAYLOAD: DEFAULT_PAYLOAD,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_VERIFY_SSL: True,
    CONF_INSECURE_CIPHER: False,
    CONF_SKIP_URL_ENCODING: False,
}
BASIC_INPUT = {
    **USER_INPUT,
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
}
BASIC_INPUT.pop(CONF_TOKEN)
DIGEST_INPUT = {
    **USER_INPUT,
    CONF_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
}
DIGEST_INPUT.pop(CONF_TOKEN)
BEARER_WITHOUT_TOKEN_INPUT = USER_INPUT.copy()
BEARER_WITHOUT_TOKEN_INPUT.pop(CONF_TOKEN)
VALID_BASIC_INPUT = {
    **BASIC_INPUT,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "password",
}
VALID_DIGEST_INPUT = {
    **DIGEST_INPUT,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "password",
}


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test setting up a Bearer-authenticated endpoint."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Primary webhook"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id is not None


async def test_user_flow_json_defaults(hass: HomeAssistant) -> None:
    """Test new endpoints suggest a valid JSON request body."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    defaults = result["data_schema"](
        {
            CONF_ENDPOINT_NAME: "Webhook",
            CONF_URL: "https://example.com/hook",
        }
    )

    assert defaults[CONF_CONTENT_TYPE] == CONTENT_TYPE_JSON
    assert defaults[CONF_PAYLOAD] == DEFAULT_PAYLOAD
    assert json.loads(defaults[CONF_PAYLOAD]) == {"message": "The event occurred"}


@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(VALID_BASIC_INPUT, id="basic"),
        pytest.param(VALID_DIGEST_INPUT, id="digest"),
    ],
)
async def test_user_flow_username_password_authentication(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> None:
    """Test setting up Basic and Digest authenticated endpoints."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == user_input
    assert CONF_TOKEN not in result["data"]


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        pytest.param(
            {**USER_INPUT, CONF_URL: "file:///tmp/hook"},
            {CONF_URL: "invalid_url"},
            id="invalid-url",
        ),
        pytest.param(
            {**USER_INPUT, CONF_URL: "https://[malformed"},
            {CONF_URL: "invalid_url"},
            id="malformed-url",
        ),
        pytest.param(
            {**USER_INPUT, CONF_URL: "https://example.com:70000/hook"},
            {CONF_URL: "invalid_url"},
            id="out-of-range-port",
        ),
        pytest.param(
            {**USER_INPUT, CONF_URL: "https://user:password@example.com/hook"},
            {CONF_URL: "userinfo_not_allowed"},
            id="userinfo-not-allowed",
        ),
        pytest.param(
            BASIC_INPUT,
            {CONF_USERNAME: "required", CONF_PASSWORD: "required"},
            id="basic-credentials-required",
        ),
        pytest.param(
            DIGEST_INPUT,
            {CONF_USERNAME: "required", CONF_PASSWORD: "required"},
            id="digest-credentials-required",
        ),
        pytest.param(
            BEARER_WITHOUT_TOKEN_INPUT,
            {CONF_TOKEN: "required"},
            id="bearer-token-required",
        ),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    errors: dict[str, str],
) -> None:
    """Test endpoint validation errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_user_flow_duplicate(hass: HomeAssistant) -> None:
    """Test duplicate method and URL prevention."""
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_preserves_bearer_token(hass: HomeAssistant) -> None:
    """Test reconfiguring without re-entering the stored token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="example.com",
        data=USER_INPUT,
        unique_id="endpoint-id",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    new_input = {
        **USER_INPUT,
        CONF_ENDPOINT_NAME: "Backup webhook",
        CONF_URL: "https://new.example.com/hook",
    }
    new_input.pop(CONF_TOKEN)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Backup webhook"
    assert entry.data[CONF_ENDPOINT_NAME] == "Backup webhook"
    assert entry.data[CONF_TOKEN] == "secret-token"


async def test_reconfigure_removes_credentials(hass: HomeAssistant) -> None:
    """Test changing to unauthenticated requests removes credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="example.com",
        data=USER_INPUT,
        unique_id="endpoint-id",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **USER_INPUT,
            CONF_AUTHENTICATION: AUTHENTICATION_NONE,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert CONF_TOKEN not in entry.data
    assert CONF_USERNAME not in entry.data
    assert CONF_PASSWORD not in entry.data
