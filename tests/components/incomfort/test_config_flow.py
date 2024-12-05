"""Tests for the Intergas InComfort config flow."""

from unittest.mock import AsyncMock, MagicMock

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
