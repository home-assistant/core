"""Test the Fjäråskupan config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.fjaraskupan.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import COOKER_SERVICE_INFO


@pytest.fixture(name="mock_setup_entry", autouse=True)
def fixture_mock_setup_entry() -> Generator[AsyncMock]:
    """Fixture for config entry."""

    with patch(
        "homeassistant.components.fjaraskupan.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_configure(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.fjaraskupan.config_flow.async_discovered_service_info",
        return_value=[COOKER_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Fjäråskupan"
        assert result["data"] == {}

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_scan_no_devices(hass: HomeAssistant) -> None:
    """Test we get the form."""

    with patch(
        "homeassistant.components.fjaraskupan.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"
