"""Tests for the Intergas InComfort config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
from incomfortclient import IncomfortError, InvalidHeaterList
import pytest

from homeassistant.components.incomfort.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_incomfort: MagicMock
) -> None:
    """Test we get the full form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Intergas InComfort/Intouch Lan2RF gateway"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_entry_already_configured(hass: HomeAssistant) -> None:
    """Test aborting if the entry is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_CONFIG[CONF_HOST],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exc", "error", "base"),
    [
        (
            IncomfortError(ClientResponseError(None, None, status=401)),
            "auth_error",
            CONF_PASSWORD,
        ),
        (
            IncomfortError(ClientResponseError(None, None, status=404)),
            "not_found",
            "base",
        ),
        (
            IncomfortError(ClientResponseError(None, None, status=500)),
            "unknown",
            "base",
        ),
        (IncomfortError, "unknown", "base"),
        (ValueError, "unknown", "base"),
        (TimeoutError, "timeout_error", "base"),
        (InvalidHeaterList, "no_heaters", "base"),
    ],
)
async def test_form_validation(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    exc: Exception,
    error: str,
    base: str,
) -> None:
    """Test form validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Simulate an issue
    mock_incomfort().heaters.side_effect = exc
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        base: error,
    }

    # Fix the issue and retry
    mock_incomfort().heaters.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "errors" not in result


@pytest.mark.parametrize(
    ("user_input", "legacy_setpoint_status"),
    [
        ({}, False),
        ({"legacy_setpoint_status": False}, False),
        ({"legacy_setpoint_status": True}, True),
    ],
)
async def test_options_flow(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    user_input: dict[str, Any],
    legacy_setpoint_status: bool,
) -> None:
    """Test options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch("homeassistant.components.incomfort.async_setup_entry") as restart_mock:
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert restart_mock.call_count == 1

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {"legacy_setpoint_status": legacy_setpoint_status}
    assert entry.options.get("legacy_setpoint_status", False) is legacy_setpoint_status
