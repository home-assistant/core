"""Tests for the Imou options flow."""

from pyimouapi.const import PARAM_HD

from homeassistant.components.imou.const import (
    CONF_OPTION_LIVE_RESOLUTION,
    CONF_OPTION_UPDATE_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test polling interval can be updated."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OPTION_LIVE_RESOLUTION: PARAM_HD,
            CONF_OPTION_UPDATE_INTERVAL: 90,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_OPTION_LIVE_RESOLUTION: PARAM_HD,
        CONF_OPTION_UPDATE_INTERVAL: 90,
    }
