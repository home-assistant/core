"""Test the Philips TV integration setup."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.philips_js import async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_VERSION, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_reconfigure_loaded_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring a loaded entry reloads it once with the new host."""
    with patch(
        "homeassistant.components.philips_js.async_setup_entry",
        wraps=async_setup_entry,
    ) as mock_setup_entry:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "2.2.2.2", CONF_API_VERSION: "1"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "2.2.2.2"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Initial setup plus a single reload by the update listener
    assert mock_setup_entry.await_count == 2
