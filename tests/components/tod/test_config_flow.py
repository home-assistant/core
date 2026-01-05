"""Test the Times of the Day config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.tod.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, get_schema_suggested_value


@pytest.mark.parametrize("platform", ["sensor"])
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.tod.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "after_time": "10:00",
                "before_time": "18:00",
                "name": "My tod",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My tod"
    assert result["data"] == {}
    assert result["options"] == {
        "after_time": "10:00",
        "before_time": "18:00",
        "name": "My tod",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "after_time": "10:00",
        "before_time": "18:00",
        "name": "My tod",
    }
    assert config_entry.title == "My tod"


@pytest.mark.freeze_time("2022-03-16 17:37:00", tz_offset=-7)
async def test_options(hass: HomeAssistant) -> None:
    """Test reconfiguring."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "after_time": "10:00",
            "before_time": "18:05",
            "name": "My tod",
        },
        title="My tod",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, "after_time") == "10:00"
    assert get_schema_suggested_value(schema, "before_time") == "18:05"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "after_time": "10:00",
            "before_time": "17:05",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "after_time": "10:00",
        "before_time": "17:05",
        "name": "My tod",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "after_time": "10:00",
        "before_time": "17:05",
        "name": "My tod",
    }
    assert config_entry.title == "My tod"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    # Check the state of the entity has changed as expected
    state = hass.states.get("binary_sensor.my_tod")
    assert state.state == "off"
    assert state.attributes["after"] == "2022-03-16T10:00:00-07:00"
    assert state.attributes["before"] == "2022-03-16T17:05:00-07:00"
