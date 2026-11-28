"""Test the Times of the Day integration."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value

from homeassistant.components.tod.binary_sensor import TodEntityStateAttribute
from homeassistant.components.tod.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


@pytest.mark.freeze_time("2022-03-16 17:37:00", tz_offset=-7)
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test setting up and removing a config entry."""
    tod_entity_id = "binary_sensor.my_tod"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "after": {"time": "10:00:00"},
            "before": {"time": "18:05:00"},
            "name": "My tod",
        },
        title="My tod",
        version=2,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(tod_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(tod_entity_id)
    # Check the state of the entity is as expected
    state = hass.states.get("binary_sensor.my_tod")
    assert state.state == "off"
    assert (
        state.attributes[TodEntityStateAttribute.AFTER] == "2022-03-16T10:00:00-07:00"
    )
    assert (
        state.attributes[TodEntityStateAttribute.BEFORE] == "2022-03-16T18:05:00-07:00"
    )

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(tod_entity_id) is None
    assert entity_registry.async_get(tod_entity_id) is None


async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test migrating V1 time-only entries and restoring their options."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "after_time": "10:00:00",
            "before_time": "18:05:00",
            "name": "My tod",
        },
        title="My tod",
        version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.options == {
        "after": {"time": "10:00:00"},
        "before": {"time": "18:05:00"},
        "name": "My tod",
    }

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, "after") == "time"
    assert get_schema_suggested_value(schema, "after_time") == "10:00:00"
    assert get_schema_suggested_value(schema, "before") == "time"
    assert get_schema_suggested_value(schema, "before_time") == "18:05:00"
