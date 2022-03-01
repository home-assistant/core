"""Test the Switch config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.switch.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.switch.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Ceiling",
                "entity_id": "switch.ceiling",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Ceiling"
    assert result["data"] == {
        "entity_id": "switch.ceiling",
        "name": "Ceiling",
    }
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]


async def test_options(hass: HomeAssistant) -> None:
    """Test reconfiguring."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None
    assert get_suggested(result["data_schema"].schema, "entity_id") is None
    assert get_suggested(result["data_schema"].schema, "name") is None

    with patch(
        "homeassistant.components.switch.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Ceiling",
                "entity_id": "switch.ceiling",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Ceiling"
    assert result["data"] == {
        "entity_id": "switch.ceiling",
        "name": "Ceiling",
    }
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert get_suggested(result["data_schema"].schema, "entity_id") == "switch.ceiling"
    assert get_suggested(result["data_schema"].schema, "name") == "Ceiling"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "Wall",
            "entity_id": "switch.wall",
        },
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] is None
    assert config_entry.data == {"name": "Wall", "entity_id": "switch.wall"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None
    assert get_suggested(result["data_schema"].schema, "entity_id") is None
    assert get_suggested(result["data_schema"].schema, "name") is None
