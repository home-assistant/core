"""Test the Min/Max config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.attribute_sensor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_config_flow(hass: HomeAssistant, platform: str) -> None:
    """Test the config flow."""
    source_entity = "sensor.one"
    source_attribute = "attribute1"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.attribute_sensor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My attribute sensor",
                "source": source_entity,
                "attribute": source_attribute,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My attribute sensor"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My attribute sensor",
        "source": source_entity,
        "attribute": source_attribute,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My attribute sensor",
        "source": source_entity,
        "attribute": source_attribute,
    }
    assert config_entry.title == "My attribute sensor"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize("platform", ("sensor",))
async def test_options(hass: HomeAssistant, platform: str) -> None:
    """Test reconfiguring."""
    hass.states.async_set("sensor.one", "10", {"attribute1": "50", "attribute2": "100"})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My attribute sensor",
            "source": "sensor.one",
            "attribute": "attribute1",
        },
        title="My attribute sensor",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "source") == "sensor.one"
    assert get_suggested(schema, "attribute") == "attribute1"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "source": "sensor.one",
            "attribute": "attribute2",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "My attribute sensor",
        "source": "sensor.one",
        "attribute": "attribute2",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My attribute sensor",
        "source": "sensor.one",
        "attribute": "attribute2",
    }
    assert config_entry.title == "My attribute sensor"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 2

    # Check the state of the entity has changed as expected
    state = hass.states.get(f"{platform}.my_attribute_sensor")
    assert state.state == "100"
