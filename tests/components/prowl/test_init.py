"""Testing the Prowl initialisation."""

from unittest.mock import Mock

import prowlpy
import pytest

from homeassistant.components.prowl.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_API_KEY

from tests.common import MockConfigEntry


async def test_load_reload_unload_config_entry(
    hass: HomeAssistant,
    mock_prowlpy_config_entry: MockConfigEntry,
    mock_prowlpy: Mock,
) -> None:
    """Test the Prowl configuration entry loading/reloading/unloading."""
    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_prowlpy_config_entry.state is ConfigEntryState.LOADED
    assert mock_prowlpy.verify_key.call_count > 0

    await hass.config_entries.async_reload(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_prowlpy_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_prowlpy_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("prowlpy_side_effect", "expected_config_state"),
    [
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (
            prowlpy.APIError(f"Invalid API key: {TEST_API_KEY}"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            prowlpy.APIError("Not accepted: exceeded rate limit"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (prowlpy.APIError("Internal server error"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_config_entry_failures(
    hass: HomeAssistant,
    mock_prowlpy_config_entry: MockConfigEntry,
    mock_prowlpy: Mock,
    prowlpy_side_effect,
    expected_config_state: ConfigEntryState,
) -> None:
    """Test the Prowl configuration entry dealing with bad API key."""
    mock_prowlpy.verify_key.side_effect = prowlpy_side_effect

    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_prowlpy_config_entry.state is expected_config_state
    assert mock_prowlpy.verify_key.call_count > 0
