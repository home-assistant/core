"""Tests for init platform of Remote Calendar."""

from unittest.mock import AsyncMock

from httpx import ConnectError, Response, UnsupportedProtocol
import pytest
import respx

from homeassistant.components.remote_calendar.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import CALENDER_URL, TEST_ENTITY

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_httpx_client: AsyncMock
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "off"

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@respx.mock
async def test_raise_for_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test update failed using respx to simulate HTTP exceptions."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=403,
        )
    )
    await setup_integration(hass, config_entry)
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "side_effect",
    [
        ConnectError("Connection failed"),
        UnsupportedProtocol("Unsupported protocol"),
        ValueError("Invalid response"),
    ],
)
@respx.mock
async def test_update_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test update failed using respx to simulate different exceptions."""
    respx.get(CALENDER_URL).mock(side_effect=side_effect)

    await setup_integration(hass, config_entry)

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
