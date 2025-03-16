"""Test the Roborock options flow."""

from unittest.mock import patch

from vacuum_map_parser_base.config.drawable import Drawable

from homeassistant.components.roborock.const import DRAWABLES
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_options_flow_drawables(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test that the options flow works."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == DRAWABLES
    with patch(
        "homeassistant.components.roborock.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={Drawable.PREDICTED_PATH: True},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert setup_entry.options[DRAWABLES][Drawable.PREDICTED_PATH] is True
    assert len(mock_setup.mock_calls) == 1
