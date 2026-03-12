"""Test the AuroraWatch UK config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.aurorawatch.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_aiohttp_session: AsyncMock,
) -> None:
    """Test full config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AuroraWatch UK"
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_already_configured(
    hass: HomeAssistant,
    mock_aiohttp_session: AsyncMock,
) -> None:
    """Test config flow aborts if already configured."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="AuroraWatch UK",
        data={},
        unique_id=DOMAIN,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
