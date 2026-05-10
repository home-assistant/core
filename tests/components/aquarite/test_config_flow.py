"""Tests for the Aquarite config flow.

These tests run in the Home Assistant Core test environment.
Run with: pytest tests/components/aquarite/test_config_flow.py
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioaquarite import AquariteError, AuthenticationError
import pytest

from homeassistant import config_entries
from homeassistant.components.aquarite.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_PASSWORD, MOCK_USERNAME

PATCH_SETUP = "homeassistant.components.aquarite.async_setup_entry"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent actual setup during config flow tests."""
    with patch(PATCH_SETUP, return_value=True) as mock:
        yield mock


async def _configure(hass: HomeAssistant) -> dict:
    """Run the user step with the standard credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )


# ── User Step ─────────────────────────────────────────────────────


async def test_user_step(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_aquarite_client: AsyncMock,
) -> None:
    """Test the user step shows a form and creates an entry on submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

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


async def test_invalid_auth(
    hass: HomeAssistant, mock_aquarite_auth: MagicMock
) -> None:
    """Test authentication error is handled."""
    mock_aquarite_auth.authenticate.side_effect = AuthenticationError

    result = await _configure(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(
    hass: HomeAssistant, mock_aquarite_auth: MagicMock
) -> None:
    """Test connectivity error during auth surfaces as cannot_connect."""
    mock_aquarite_auth.authenticate.side_effect = AquariteError("network down")

    result = await _configure(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_cannot_connect_during_pool_fetch(
    hass: HomeAssistant, mock_aquarite_client: AsyncMock
) -> None:
    """Test connectivity error while fetching pools surfaces as cannot_connect."""
    mock_aquarite_client.get_pools = AsyncMock(
        side_effect=AquariteError("network down")
    )

    result = await _configure(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unknown_exception_during_pool_fetch(
    hass: HomeAssistant, mock_aquarite_client: AsyncMock
) -> None:
    """Test unexpected error while fetching pools surfaces as unknown."""
    mock_aquarite_client.get_pools = AsyncMock(side_effect=RuntimeError("boom"))

    result = await _configure(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_unknown_exception(
    hass: HomeAssistant, mock_aquarite_auth: MagicMock
) -> None:
    """Test unknown error during auth is handled."""
    mock_aquarite_auth.authenticate.side_effect = RuntimeError("Connection refused")

    result = await _configure(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_no_pools(
    hass: HomeAssistant, mock_aquarite_client: AsyncMock
) -> None:
    """Test that an account with no pools shows the no_pools error."""
    mock_aquarite_client.get_pools = AsyncMock(return_value={})

    result = await _configure(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_pools"}


async def test_duplicate_account_aborts(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_aquarite_client: AsyncMock,
) -> None:
    """Test that adding the same account twice aborts."""
    # First entry
    result = await _configure(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Same account again
    result = await _configure(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
