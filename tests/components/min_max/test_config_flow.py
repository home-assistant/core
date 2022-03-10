"""Test the Min/Max config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.min_max.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form_minimum_fields(hass: HomeAssistant) -> None:
    """Test we get the form and minimum fields work."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.min_max.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Max sensor"
    assert result2["data"] == {
        "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        "name": "Max sensor",
        "round_digits": 2,
        "type": "max",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_all_fields(hass: HomeAssistant) -> None:
    """Test we get the form and all fields work."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.min_max.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
                "name": "Max sensor",
                "round_digits": 2,
                "type": "max",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Max sensor"
    assert result2["data"] == {
        "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        "name": "Max sensor",
        "round_digits": 2,
        "type": "max",
    }
    assert len(mock_setup_entry.mock_calls) == 1
