"""Test the photoptimizer config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.photoptimizer.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.parametrize("platform", ["sensor"])
async def test_config_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, platform
) -> None:
    """Test the config flow."""
    input_sensor_entity_id = "sensor.input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "My photoptimizer", "entity_id": input_sensor_entity_id},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My photoptimizer"
    assert result["data"] == {}
    assert result["options"] == {
        "entity_id": input_sensor_entity_id,
        "name": "My photoptimizer",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": input_sensor_entity_id,
        "name": "My photoptimizer",
    }
    assert config_entry.title == "My photoptimizer"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise KeyError(f"Key `{key}` is missing from schema")


@pytest.mark.parametrize("platform", ["sensor"])
async def test_options(hass: HomeAssistant, platform) -> None:
    """Test reconfiguring."""
    input_sensor_1_entity_id = "sensor.input1"
    input_sensor_2_entity_id = "sensor.input2"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": input_sensor_1_entity_id,
            "name": "My photoptimizer",
        },
        title="My photoptimizer",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "entity_id") == input_sensor_1_entity_id

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entity_id": input_sensor_2_entity_id,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entity_id": input_sensor_2_entity_id,
        "name": "My photoptimizer",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": input_sensor_2_entity_id,
        "name": "My photoptimizer",
    }
    assert config_entry.title == "My photoptimizer"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    state = hass.states.get(f"{platform}.my_photoptimizer")
    assert state.attributes == {}
