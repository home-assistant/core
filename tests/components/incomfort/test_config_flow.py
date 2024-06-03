"""Tests for the Intergas InComfort config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponseError
from incomfortclient import IncomfortError
import pytest

from homeassistant.components.incomfort import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    "host": "192.168.1.12",
    "username": "admin",
    "password": "verysecret",
}


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_incomfort: MagicMock
) -> None:
    """Test we get the full form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Intergas InComfort/Intouch Lan2RF gateway"
    assert result2["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_incomfort: MagicMock
) -> None:
    """Test we van import from YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Intergas InComfort/Intouch Lan2RF gateway"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "abort_reason"),
    [
        (IncomfortError(ClientResponseError(None, None, status=401)), "auth_error"),
        (IncomfortError(ClientResponseError(None, None, status=404)), "not_found"),
        (IncomfortError(ClientResponseError(None, None, status=500)), "unknown"),
        (TimeoutError, "timeout_error"),
    ],
)
async def test_import_fails(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_incomfort: MagicMock,
    exc: Exception,
    abort_reason: str,
) -> None:
    """Test YAML import fails."""
    mock_incomfort().heaters.side_effect = exc
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason
    assert len(mock_setup_entry.mock_calls) == 0


async def test_entry_already_configured(hass: HomeAssistant) -> None:
    """Test aborting if the entry is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_CONFIG[CONF_HOST],
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


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
        (TimeoutError, "timeout_error", "base"),
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

    # Simulate issue and retry
    mock_incomfort().heaters.side_effect = exc
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {
        base: error,
    }

    # Fix the issue and retry
    mock_incomfort().heaters.side_effect = None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert "errors" not in result2
