"""Tests for the Ollama coordinator."""

from unittest.mock import AsyncMock, patch

import ollama
import pytest

from homeassistant.components.ollama.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize("status_code", [401, 403])
@patch("ollama.AsyncClient.list", return_value=ollama.ListResponse(models=[]))
@patch("ollama.AsyncClient.ps", return_value=ollama.ProcessResponse(models=[]))
async def test_auth_failure_triggers_reauth(
    mock_ps: AsyncMock,
    mock_list: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    status_code: int,
) -> None:
    """Test an authentication failure during polling triggers reauthentication."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_ps.side_effect = ollama.ResponseError("Unauthorized", status_code=status_code)
    await mock_config_entry.runtime_data.async_refresh()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"].get("source") == SOURCE_REAUTH for flow in flows)
    assert mock_list.await_count == 2
