"""Tests for the Risco initialization."""
import pytest

from homeassistant.components.risco import CannotConnectError
from homeassistant.components.risco.const import CONF_COMMUNICATION_DELAY
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize("exception", [CannotConnectError])
async def test_single_error_on_connect(
    hass: HomeAssistant, connect_with_single_error, local_config_entry
) -> None:
    """Test single error on connect to validate communication delay update from 0 (default) to 1."""
    expected_data = {
        **local_config_entry.data,
        **{"type": "local", CONF_COMMUNICATION_DELAY: 1},
    }

    await hass.config_entries.async_setup(local_config_entry.entry_id)
    await hass.async_block_till_done()
    assert local_config_entry.data == expected_data
