"""Tests for the Aquarite config flow.

These tests run in the Home Assistant Core test environment.
Run with: pytest tests/components/aquarite/test_config_flow.py
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aioaquarite import AquariteError, AuthenticationError
import pytest

from homeassistant import config_entries
from homeassistant.components.aquarite.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_PASSWORD, MOCK_USER_ID, MOCK_USERNAME

PATCH_AUTH = "homeassistant.components.aquarite.config_flow.AquariteAuth"
PATCH_CLIENT = "homeassistant.components.aquarite.config_flow.AquariteClient"
PATCH_SETUP = "homeassistant.components.aquarite.async_setup_entry"

MOCK_POOLS = {"pool-1": "Main Pool"}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent actual setup during config flow tests."""
    with patch(PATCH_SETUP, return_value=True) as mock:
        yield mock


# ── User Step ─────────────────────────────────────────────────────


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows the auth form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful authentication creates an entry."""
    with (
        patch(PATCH_AUTH) as mock_auth_cls,
        patch(PATCH_CLIENT) as mock_client_cls,
    ):
        mock_auth = AsyncMock()
        mock_auth.user_id = MOCK_USER_ID
        mock_auth_cls.return_value = mock_auth
        mock_client = AsyncMock()
        mock_client.get_pools = AsyncMock(return_value=MOCK_POOLS)
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
    }


# ── Error Handling ────────────────────────────────────────────────


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test authentication error is handled."""
    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AuthenticationError
        mock_auth_cls.return_value = mock_auth

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test connectivity error during auth surfaces as cannot_connect."""
    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AquariteError("network down")
        mock_auth_cls.return_value = mock_auth

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unknown_exception(hass: HomeAssistant) -> None:
    """Test unknown error during auth is handled."""
    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = RuntimeError("Connection refused")
        mock_auth_cls.return_value = mock_auth

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_no_pools(hass: HomeAssistant) -> None:
    """Test that an account with no pools shows the no_pools error."""
    with (
        patch(PATCH_AUTH) as mock_auth_cls,
        patch(PATCH_CLIENT) as mock_client_cls,
    ):
        mock_auth_cls.return_value = AsyncMock()
        mock_client = AsyncMock()
        mock_client.get_pools = AsyncMock(return_value={})
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_pools"}


async def test_duplicate_account_aborts(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that adding the same account twice aborts."""
    with (
        patch(PATCH_AUTH) as mock_auth_cls,
        patch(PATCH_CLIENT) as mock_client_cls,
    ):
        mock_auth = AsyncMock()
        mock_auth.user_id = MOCK_USER_ID
        mock_auth_cls.return_value = mock_auth
        mock_client = AsyncMock()
        mock_client.get_pools = AsyncMock(return_value=MOCK_POOLS)
        mock_client_cls.return_value = mock_client

        # First entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # Same account again
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
