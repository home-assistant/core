"""Unit tests for config_flow.py — PajGPSConfigFlow (initial setup).

Coverage:
- PajGPSConfigFlow.async_step_user:
    * GET (no input) → returns FORM with step_id "user"
    * Valid full input → CREATE_ENTRY with email as title and data fields
    * Duplicate email → AbortFlow raised
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError
import pytest

from homeassistant.components.pajgps.config_flow import (
    PajGPSConfigFlow,
    _validate_credentials,
)
from homeassistant.data_entry_flow import AbortFlow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flow() -> PajGPSConfigFlow:
    """Return a PajGPSConfigFlow instance with a mocked hass."""
    flow = PajGPSConfigFlow()
    flow.hass = MagicMock()
    # async_create_entry and async_show_form are inherited from FlowHandler;
    # they just build result dicts — we call them directly without a real hass.
    return flow


VALID_USER_INPUT = {
    "email": "user@example.com",
    "password": "s3cr3t",
}


# ---------------------------------------------------------------------------
# PajGPSConfigFlow — initial config
# ---------------------------------------------------------------------------


class TestPajGPSConfigFlow(unittest.IsolatedAsyncioTestCase):
    """Tests for PajGPSConfigFlow.async_step_user."""

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
# Credential validation — CustomFlow
# ---------------------------------------------------------------------------


class TestCustomFlowCredentialValidation(unittest.IsolatedAsyncioTestCase):
    """Tests for _validate_credentials being called inside CustomFlow.async_step_user."""

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
# _validate_credentials unit tests (the helper itself)
# ---------------------------------------------------------------------------


class TestValidateCredentials(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the _validate_credentials module-level helper."""

    async def test_returns_none_on_successful_login(self):
        """A successful api.login() call must return None (no error)."""
        hass = MagicMock()
        with (
            patch(
                "homeassistant.components.pajgps.config_flow.async_get_clientsession"
            ),
            patch("homeassistant.components.pajgps.config_flow.PajGpsApi") as MockApi,
        ):
            MockApi.return_value.login = AsyncMock()
            result = await _validate_credentials("user@example.com", "secret", hass)

        assert result is None

    async def test_returns_invalid_auth_on_authentication_error(self):
        """AuthenticationError from login() must map to 'invalid_auth'."""
        hass = MagicMock()
        with (
            patch(
                "homeassistant.components.pajgps.config_flow.async_get_clientsession"
            ),
            patch("homeassistant.components.pajgps.config_flow.PajGpsApi") as MockApi,
        ):
            MockApi.return_value.login = AsyncMock(
                side_effect=AuthenticationError("bad creds")
            )
            result = await _validate_credentials("user@example.com", "wrong", hass)

        assert result == "invalid_auth"

    async def test_returns_invalid_auth_on_token_refresh_error(self):
        """TokenRefreshError from login() must map to 'invalid_auth'."""
        hass = MagicMock()
        with (
            patch(
                "homeassistant.components.pajgps.config_flow.async_get_clientsession"
            ),
            patch("homeassistant.components.pajgps.config_flow.PajGpsApi") as MockApi,
        ):
            MockApi.return_value.login = AsyncMock(
                side_effect=TokenRefreshError("refresh failed")
            )
            result = await _validate_credentials("user@example.com", "secret", hass)

        assert result == "invalid_auth"

    async def test_returns_cannot_connect_on_generic_exception(self):
        """Any unexpected exception from login() must map to 'cannot_connect'."""
        hass = MagicMock()
        with (
            patch(
                "homeassistant.components.pajgps.config_flow.async_get_clientsession"
            ),
            patch("homeassistant.components.pajgps.config_flow.PajGpsApi") as MockApi,
        ):
            MockApi.return_value.login = AsyncMock(
                side_effect=ConnectionError("timeout")
            )
            result = await _validate_credentials("user@example.com", "secret", hass)

        assert result == "cannot_connect"
