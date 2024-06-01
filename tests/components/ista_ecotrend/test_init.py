"""Test the ista Ecotrend init."""

from unittest.mock import MagicMock

from pyecotrend_ista.exception_classes import InternalServerError, ServerError
import pytest
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_entry_setup_unload(
    hass: HomeAssistant, ista_config_entry: MockConfigEntry, mock_ista: MagicMock
) -> None:
    """Test integration setup and unload."""

    ista_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect"),
    [ServerError, InternalServerError, RequestException, TimeoutError],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
    mock_ista: MagicMock,
    side_effect: Exception,
) -> None:
    """Test config entry not ready."""
    mock_ista.login.side_effect = ServerError
    ista_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.SETUP_RETRY
