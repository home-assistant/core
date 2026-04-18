"""Tests for emulated_roku config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.emulated_roku import config_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.emulated_roku.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def test_flow_works(hass: HomeAssistant) -> None:
    """Test that config flow works."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"name": "Emulated Roku Test", "listen_port": 8060},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Emulated Roku Test"
    assert result["data"] == {"name": "Emulated Roku Test", "listen_port": 8060}


async def test_flow_already_registered_entry(hass: HomeAssistant) -> None:
    """Test that config flow doesn't allow existing names."""
    MockConfigEntry(
        domain="emulated_roku", data={"name": "Emulated Roku Test", "listen_port": 8062}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"name": "Emulated Roku Test", "listen_port": 8062},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
