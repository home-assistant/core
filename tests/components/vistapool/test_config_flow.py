"""Tests for the Vistapool config flow.

These tests run in the Home Assistant Core test environment.
Run with: pytest tests/components/vistapool/test_config_flow.py
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioaquarite import AquariteError, AuthenticationError
import pytest

from homeassistant import config_entries
from homeassistant.components.vistapool.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_PASSWORD, MOCK_POOLS, MOCK_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent actual setup during config flow tests."""
    with patch(
        "homeassistant.components.vistapool.async_setup_entry", return_value=True
    ) as mock:
        yield mock


async def _submit(hass: HomeAssistant, flow_id: str) -> dict:
    """Submit the user step with the standard credentials."""
    return await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )


async def _configure(hass: HomeAssistant) -> dict:
    """Run the user step from start to finish with the standard credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await _submit(hass, result["flow_id"])


# ── User Step ─────────────────────────────────────────────────────


async def test_user_step(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the user step shows a form and creates an entry on submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
    }


# ── Error Handling (each path also verifies the flow can recover) ─


async def test_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vistapool_client: AsyncMock,
    mock_vistapool_auth: MagicMock,
) -> None:
    """Test the flow surfaces invalid_auth and recovers on retry."""
    mock_vistapool_auth.authenticate.side_effect = AuthenticationError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Recover: clear the failure and retry the same flow.
    mock_vistapool_auth.authenticate.side_effect = None
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME


async def test_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vistapool_client: AsyncMock,
    mock_vistapool_auth: MagicMock,
) -> None:
    """Test cannot_connect on auth failure and recovery on retry."""
    mock_vistapool_auth.authenticate.side_effect = AquariteError("network down")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_vistapool_auth.authenticate.side_effect = None
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME


async def test_cannot_connect_during_pool_fetch(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test cannot_connect on get_pools failure and recovery on retry."""
    mock_vistapool_client.get_pools.side_effect = AquariteError("network down")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_vistapool_client.get_pools.side_effect = None
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME


async def test_unknown_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vistapool_client: AsyncMock,
    mock_vistapool_auth: MagicMock,
) -> None:
    """Test unknown error on auth failure and recovery on retry."""
    mock_vistapool_auth.authenticate.side_effect = RuntimeError("Connection refused")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_vistapool_auth.authenticate.side_effect = None
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME


async def test_unknown_exception_during_pool_fetch(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test unknown error on get_pools failure and recovery on retry."""
    mock_vistapool_client.get_pools.side_effect = RuntimeError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_vistapool_client.get_pools.side_effect = None
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME


async def test_no_pools(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test no_pools on an empty account and recovery once pools appear."""
    mock_vistapool_client.get_pools.return_value = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_pools"}

    # Recover: pools appear on the account; resubmit the same flow.
    mock_vistapool_client.get_pools.return_value = MOCK_POOLS
    result = await _submit(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME


async def test_duplicate_account_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the flow aborts when an entry for the account already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await _configure(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
