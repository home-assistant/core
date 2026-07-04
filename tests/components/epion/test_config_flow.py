"""Tests for the Epion config flow."""

from unittest.mock import MagicMock, patch

from epion import EpionAuthenticationError, EpionConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.epion.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

API_KEY = "test-key-123"


async def test_user_flow(hass: HomeAssistant, mock_epion: MagicMock) -> None:
    """Test we can handle a regular successflow setup flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epion.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Epion integration"
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (EpionAuthenticationError("Invalid auth"), "invalid_auth"),
        (EpionConnectionError("Timeout error"), "cannot_connect"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant, exception: Exception, error: str, mock_epion: MagicMock
) -> None:
    """Test we can handle Form exceptions."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_epion.return_value.get_current.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_epion.return_value.get_current.side_effect = None

    with patch(
        "homeassistant.components.epion.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Epion integration"
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant, mock_epion: MagicMock) -> None:
    """Test duplicate setup handling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: API_KEY,
        },
        unique_id="account-dupe-123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: API_KEY},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
