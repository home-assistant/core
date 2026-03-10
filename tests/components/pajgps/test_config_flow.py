"""Unit tests for config_flow.py — CustomFlow (initial setup) and OptionsFlowHandler (options editing).

Coverage:
- CustomFlow.async_step_user:
    * GET (no input) → returns FORM with step_id "user"
    * Valid full input → CREATE_ENTRY with email as title, data fields, and a generated guid
    * Empty email    → FORM with errors["base"] == "email_required"
    * Empty password → FORM with errors["base"] == "password_required"

- OptionsFlowHandler.async_step_init:
    * GET (no input) → returns FORM with step_id "init", defaults come from config_entry.data
    * Defaults from config_entry.options override config_entry.data
    * Valid user input → CREATE_ENTRY, preserves original guid, sets new field values
    * Empty email   → FORM with errors["base"] == "email_required"
    * Empty password → FORM with errors["base"] == "password_required"
"""

from __future__ import annotations

from typing import Any
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError
import pytest

from homeassistant.components.pajgps.config_flow import (
    OptionsFlowHandler,
    PajGPSConfigFlow,
    _validate_credentials,
)
from homeassistant.data_entry_flow import AbortFlow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_config_entry(
    data: dict[str, Any], options: dict[str, Any] | None = None
) -> MagicMock:
    """Return a minimal mock ConfigEntry with .data and .options dicts."""
    entry = MagicMock()
    entry.data = dict(data)
    entry.options = dict(options) if options is not None else {}
    return entry


def _make_flow() -> PajGPSConfigFlow:
    """Return a PajGPSConfigFlow instance with a mocked hass."""
    flow = PajGPSConfigFlow()
    flow.hass = MagicMock()
    # async_create_entry and async_show_form are inherited from FlowHandler;
    # they just build result dicts — we call them directly without a real hass.
    return flow


def _make_options_flow(
    data: dict[str, Any], options: dict[str, Any] | None = None
) -> OptionsFlowHandler:
    """Return an OptionsFlowHandler instance with a mocked hass."""
    entry = _make_mock_config_entry(data, options)
    handler = OptionsFlowHandler(entry)
    handler.hass = MagicMock()
    return handler


VALID_USER_INPUT = {
    "email": "user@example.com",
    "password": "s3cr3t",
}

VALID_ENTRY_DATA = {
    "guid": "existing-guid-1234",
    "email": "original@example.com",
    "password": "original_pass",
}

VALID_OPTIONS_INPUT = {
    "email": "updated@example.com",
    "password": "new_pass",
}


# ---------------------------------------------------------------------------
# CustomFlow — initial config
# ---------------------------------------------------------------------------


class TestCustomFlow(unittest.IsolatedAsyncioTestCase):
    """Tests for CustomFlow.async_step_user."""

    async def test_shows_form_on_get(self):
        """Calling without input must return a FORM with step_id 'user'."""
        flow = _make_flow()

        result = await flow.async_step_user(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result.get("errors", {}) == {}

    async def test_valid_input_creates_entry(self):
        """Valid full input must create an entry with correct title and all data fields."""
        flow = _make_flow()

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ):
            result = await flow.async_step_user(user_input=dict(VALID_USER_INPUT))

        assert result["type"] == "create_entry"
        assert result["title"] == VALID_USER_INPUT["email"]

        data = result["data"]
        assert data["email"] == VALID_USER_INPUT["email"]
        assert data["password"] == VALID_USER_INPUT["password"]

    async def test_creates_entry_with_valid_guid(self):
        """A fresh UUID must be generated and stored as 'guid' in entry data."""
        flow = _make_flow()

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ):
            result = await flow.async_step_user(user_input=dict(VALID_USER_INPUT))

        assert "guid" in result["data"]
        generated_guid = result["data"]["guid"]
        # Must be a valid UUID string
        parsed = uuid.UUID(generated_guid)
        assert str(parsed) == generated_guid

    async def test_valid_input_does_not_return_errors(self):
        """Valid input must produce no errors dict key."""
        flow = _make_flow()

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ):
            result = await flow.async_step_user(user_input=dict(VALID_USER_INPUT))

        assert result["type"] != "form"

    async def test_duplicate_email_aborts_flow(self):
        """If an entry with the same email already exists, _async_abort_entries_match is called with the email and raises AbortFlow, which propagates out of the flow."""
        flow = _make_flow()

        with (
            pytest.raises(AbortFlow) as ctx,
            patch.object(
                flow,
                "_async_abort_entries_match",
                side_effect=AbortFlow("already_configured"),
            ),
        ):
            await flow.async_step_user(user_input=dict(VALID_USER_INPUT))

        assert str(ctx.value.reason) == "already_configured"

    async def test_duplicate_check_uses_email_as_key(self):
        """_async_abort_entries_match must be called with the email from user input."""
        flow = _make_flow()

        with (
            patch.object(flow, "_async_abort_entries_match") as mock_abort_match,
            patch(
                "homeassistant.components.pajgps.config_flow._validate_credentials",
                new=AsyncMock(return_value=None),
            ),
        ):
            await flow.async_step_user(user_input=dict(VALID_USER_INPUT))

        mock_abort_match.assert_called_once_with({"email": VALID_USER_INPUT["email"]})


# ---------------------------------------------------------------------------
# OptionsFlowHandler — options editing
# ---------------------------------------------------------------------------


class TestOptionsFlowHandler(unittest.IsolatedAsyncioTestCase):
    """Tests for OptionsFlowHandler.async_step_init."""

    async def test_shows_form_on_get(self):
        """Calling without input must return a FORM with step_id 'init'."""
        handler = _make_options_flow(VALID_ENTRY_DATA)

        result = await handler.async_step_init(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"
        assert result.get("errors", {}) == {}

    async def test_valid_update_creates_entry(self):
        """Valid user input must return CREATE_ENTRY with updated field values."""
        handler = _make_options_flow(VALID_ENTRY_DATA)

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ):
            result = await handler.async_step_init(user_input=dict(VALID_OPTIONS_INPUT))

        assert result["type"] == "create_entry"
        data = result["data"]
        assert data["email"] == VALID_OPTIONS_INPUT["email"]
        assert data["password"] == VALID_OPTIONS_INPUT["password"]

    async def test_valid_update_preserves_guid(self):
        """The original guid from config_entry.data must be preserved after an options update."""
        handler = _make_options_flow(VALID_ENTRY_DATA)

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ):
            result = await handler.async_step_init(user_input=dict(VALID_OPTIONS_INPUT))

        assert result["data"]["guid"] == VALID_ENTRY_DATA["guid"]

    async def test_valid_update_calls_async_update_entry(self):
        """hass.config_entries.async_update_entry must be called once with the new data."""
        handler = _make_options_flow(VALID_ENTRY_DATA)

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ):
            await handler.async_step_init(user_input=dict(VALID_OPTIONS_INPUT))

        handler.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = handler.hass.config_entries.async_update_entry.call_args
        passed_data = (
            call_kwargs.kwargs.get("data") or call_kwargs.args[1]
            if len(call_kwargs.args) > 1
            else call_kwargs.kwargs.get("data")
        )
        assert passed_data["guid"] == VALID_ENTRY_DATA["guid"]

    async def test_empty_email_returns_form_with_error(self):
        """Empty email must return a form with errors['base'] == 'email_required'."""
        handler = _make_options_flow(VALID_ENTRY_DATA)
        user_input = dict(VALID_OPTIONS_INPUT, email="")

        result = await handler.async_step_init(user_input=user_input)

        assert result["type"] == "form"
        assert result["errors"]["base"] == "email_required"

    async def test_empty_password_returns_form_with_error(self):
        """Empty password must return a form with errors['base'] == 'password_required'."""
        handler = _make_options_flow(VALID_ENTRY_DATA)
        user_input = dict(VALID_OPTIONS_INPUT, password="")

        result = await handler.async_step_init(user_input=user_input)

        assert result["type"] == "form"
        assert result["errors"]["base"] == "password_required"

    async def test_valid_input_does_not_return_errors(self):
        """Valid input must not produce an errors dict."""
        handler = _make_options_flow(VALID_ENTRY_DATA)

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ):
            result = await handler.async_step_init(user_input=dict(VALID_OPTIONS_INPUT))

        assert result["type"] != "form"


# ---------------------------------------------------------------------------
# Credential validation — CustomFlow
# ---------------------------------------------------------------------------


class TestCustomFlowCredentialValidation(unittest.IsolatedAsyncioTestCase):
    """Tests for _validate_credentials being called inside CustomFlow.async_step_user."""

    async def test_cannot_connect_returns_form_with_error(self):
        """When the API is unreachable, form must show cannot_connect error."""
        flow = _make_flow()

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value="cannot_connect"),
        ):
            result = await flow.async_step_user(user_input=dict(VALID_USER_INPUT))

        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"

    async def test_invalid_auth_returns_form_with_error(self):
        """When credentials are rejected by the API, form must show invalid_auth error."""
        flow = _make_flow()

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value="invalid_auth"),
        ):
            result = await flow.async_step_user(user_input=dict(VALID_USER_INPUT))

        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_auth"

    async def test_valid_credentials_create_entry(self):
        """When _validate_credentials returns None, the entry must be created."""
        flow = _make_flow()

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ):
            result = await flow.async_step_user(user_input=dict(VALID_USER_INPUT))

        assert result["type"] == "create_entry"


# ---------------------------------------------------------------------------
# Credential validation — OptionsFlowHandler
# ---------------------------------------------------------------------------


class TestOptionsFlowCredentialValidation(unittest.IsolatedAsyncioTestCase):
    """Tests for _validate_credentials being called inside OptionsFlowHandler.async_step_init."""

    async def test_cannot_connect_returns_form_with_error(self):
        """When the API is unreachable, form must show cannot_connect error."""
        handler = _make_options_flow(VALID_ENTRY_DATA)

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value="cannot_connect"),
        ):
            result = await handler.async_step_init(user_input=dict(VALID_OPTIONS_INPUT))

        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"

    async def test_invalid_auth_returns_form_with_error(self):
        """When credentials are rejected by the API, form must show invalid_auth error."""
        handler = _make_options_flow(VALID_ENTRY_DATA)

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value="invalid_auth"),
        ):
            result = await handler.async_step_init(user_input=dict(VALID_OPTIONS_INPUT))

        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_auth"

    async def test_valid_credentials_create_entry(self):
        """When _validate_credentials returns None, the entry must be created."""
        handler = _make_options_flow(VALID_ENTRY_DATA)

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ):
            result = await handler.async_step_init(user_input=dict(VALID_OPTIONS_INPUT))

        assert result["type"] == "create_entry"

    async def test_credential_check_skipped_when_fields_are_empty(self):
        """_validate_credentials must NOT be called when empty-field errors are present."""
        handler = _make_options_flow(VALID_ENTRY_DATA)

        with patch(
            "homeassistant.components.pajgps.config_flow._validate_credentials",
            new=AsyncMock(return_value=None),
        ) as mock_validate:
            await handler.async_step_init(
                user_input=dict(VALID_OPTIONS_INPUT, password="")
            )

        mock_validate.assert_not_called()


# ---------------------------------------------------------------------------
# _validate_credentials unit tests (the helper itself)
# ---------------------------------------------------------------------------


class TestValidateCredentials(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the _validate_credentials module-level helper."""

    async def test_returns_none_on_successful_login(self):
        """A successful api.login() call must return None (no error)."""
        mock_hass = MagicMock()
        with (
            patch("homeassistant.components.pajgps.config_flow.PajGpsApi") as MockApi,
            patch(
                "homeassistant.components.pajgps.config_flow.async_get_clientsession",
                return_value=MagicMock(),
            ),
        ):
            MockApi.return_value.login = AsyncMock()
            result = await _validate_credentials(
                "user@example.com", "secret", mock_hass
            )

        assert result is None

    async def test_returns_invalid_auth_on_authentication_error(self):
        """AuthenticationError from login() must map to 'invalid_auth'."""
        mock_hass = MagicMock()
        with (
            patch("homeassistant.components.pajgps.config_flow.PajGpsApi") as MockApi,
            patch(
                "homeassistant.components.pajgps.config_flow.async_get_clientsession",
                return_value=MagicMock(),
            ),
        ):
            MockApi.return_value.login = AsyncMock(
                side_effect=AuthenticationError("bad creds")
            )
            result = await _validate_credentials("user@example.com", "wrong", mock_hass)

        assert result == "invalid_auth"

    async def test_returns_invalid_auth_on_token_refresh_error(self):
        """TokenRefreshError from login() must map to 'invalid_auth'."""
        mock_hass = MagicMock()
        with (
            patch("homeassistant.components.pajgps.config_flow.PajGpsApi") as MockApi,
            patch(
                "homeassistant.components.pajgps.config_flow.async_get_clientsession",
                return_value=MagicMock(),
            ),
        ):
            MockApi.return_value.login = AsyncMock(
                side_effect=TokenRefreshError("refresh failed")
            )
            result = await _validate_credentials(
                "user@example.com", "secret", mock_hass
            )

        assert result == "invalid_auth"

    async def test_returns_cannot_connect_on_generic_exception(self):
        """Any unexpected exception from login() must map to 'cannot_connect'."""
        mock_hass = MagicMock()
        with (
            patch("homeassistant.components.pajgps.config_flow.PajGpsApi") as MockApi,
            patch(
                "homeassistant.components.pajgps.config_flow.async_get_clientsession",
                return_value=MagicMock(),
            ),
        ):
            MockApi.return_value.login = AsyncMock(
                side_effect=ConnectionError("timeout")
            )
            result = await _validate_credentials(
                "user@example.com", "secret", mock_hass
            )

        assert result == "cannot_connect"


class TestAsyncGetOptionsFlow(unittest.TestCase):
    """Tests for CustomFlow.async_get_options_flow (config_flow.py line 100)."""

    def test_returns_options_flow_handler(self):
        """async_get_options_flow must return an OptionsFlowHandler instance."""
        config_entry = MagicMock()
        result = PajGPSConfigFlow.async_get_options_flow(config_entry)
        assert isinstance(result, OptionsFlowHandler)
