"""Tests for the Intergas InComfort config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components.incomfort import DOMAIN
from homeassistant.const import CONF_PASSWORD
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
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

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
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=MOCK_CONFIG
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
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": MOCK_CONFIG["host"],
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("status", "error", "base"),
    [
        (401, "auth_error", CONF_PASSWORD),
        (404, "not_found", "base"),
        (500, "unknown_error", "base"),
    ],
)
async def test_form_invalid_auth(
    hass: HomeAssistant, mock_incomfort: MagicMock, status: int, error: str, base: str
) -> None:
    """Test we handle client response errors correctly."""
    # pylint: disable-next=import-outside-toplevel
    from incomfortclient import IncomfortError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_incomfort().heaters.side_effect = IncomfortError(
        ClientResponseError(None, None, status=status)
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {
        base: error,
    }


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (TimeoutError, "timeout_error"),
        (ValueError("some value error"), "unknown_error"),
    ],
)
async def test_form_cannot_connect(
    hass: HomeAssistant, mock_incomfort: MagicMock, exc: Exception, error: str
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_incomfort().heaters.side_effect = exc
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}
