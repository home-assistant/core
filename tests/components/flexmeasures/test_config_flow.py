"""Test the FlexMeasures config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.flexmeasures.const import DOMAIN
from homeassistant.core import HomeAssistant

CONFIG = {
    "username": "admin@admin.com",
    "password": "admin",
    "host": "localhost:5000",
    "power_sensor": 1,
    "price_sensor": 2,
    "soc_sensor": 3,
    "rm_discharge_sensor": 4,
    "schedule_duration": 5,
}


async def test_form(hass: HomeAssistant) -> None:
    """Test that the form pops up on loading."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert (result["errors"] == {}) or result["errors"] is None

    with patch(
        "homeassistant.components.flexmeasures.config_flow.validate_input",
        return_value={"title": "FlexMeasures"},
    ) as mock_validate_input, patch(
        "homeassistant.components.flexmeasures.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "FlexMeasures"
    assert result2["data"] == CONFIG

    mock_setup_entry.assert_called_once()
    mock_validate_input.assert_called_once()
