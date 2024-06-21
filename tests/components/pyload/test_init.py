"""Test pyLoad init."""

from unittest.mock import MagicMock

from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_pyloadapi")
async def test_entry_setup_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect"),
    [CannotConnect, ParserError, InvalidAuth],
)
async def test_config_entry_setup_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: MagicMock,
    side_effect: Exception,
) -> None:
    """Test config entry not ready."""
    mock_pyloadapi.login.side_effect = side_effect
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
