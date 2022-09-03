"""Test the Utility Cost config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.utility_cost.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.parametrize("platform", ("sensor",))
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    utility_input_sensor_entity_id = "sensor.utility_input"
    price_input_sensor_entity_id = "sensor.price_input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.utility_cost.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My utility cost",
                "utility_source": utility_input_sensor_entity_id,
                "price_source": price_input_sensor_entity_id,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My utility cost"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My utility cost",
        "utility_source": "sensor.utility_input",
        "price_source": "sensor.price_input",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My utility cost",
        "utility_source": "sensor.utility_input",
        "price_source": "sensor.price_input",
    }
    assert config_entry.title == "My utility cost"
