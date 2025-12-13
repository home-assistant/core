"""Test the Times of the Day config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.tod.const import (
    CONF_AFTER_KIND,
    CONF_AFTER_OFFSET_MIN,
    CONF_AFTER_TIME,
    CONF_BEFORE_KIND,
    CONF_BEFORE_OFFSET_MIN,
    CONF_BEFORE_TIME,
    DOMAIN,
    KIND_FIXED,
    TodKind,
)
from homeassistant.const import (
    CONF_AFTER,
    CONF_BEFORE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, get_schema_suggested_value

AFTER_FIXED = "after_fixed"
BEFORE_FIXED = "before_fixed"
KIND_SUNRISE = "sunrise"
KIND_SUNSET = "sunset"


@pytest.mark.parametrize("platform", ["sensor"])
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "My tod",
            CONF_AFTER_KIND: KIND_FIXED,
            CONF_BEFORE_KIND: KIND_FIXED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == AFTER_FIXED

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AFTER_TIME: "10:00"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == BEFORE_FIXED

    with patch(
        "homeassistant.components.tod.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BEFORE_TIME: "18:00"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My tod"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My tod",
        CONF_AFTER_KIND: KIND_FIXED,
        CONF_AFTER_TIME: "10:00",
        CONF_AFTER_OFFSET_MIN: 0,
        CONF_BEFORE_KIND: KIND_FIXED,
        CONF_BEFORE_TIME: "18:00",
        CONF_BEFORE_OFFSET_MIN: 0,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == result["options"]
    assert config_entry.title == "My tod"


@pytest.mark.freeze_time("2022-03-16 17:37:00", tz_offset=-7)
async def test_options(hass: HomeAssistant) -> None:
    """Test reconfiguring."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My tod",
            CONF_AFTER_KIND: KIND_FIXED,
            CONF_AFTER_TIME: "10:00",
            CONF_AFTER_OFFSET_MIN: 0,
            CONF_BEFORE_KIND: KIND_FIXED,
            CONF_BEFORE_TIME: "18:05",
            CONF_BEFORE_OFFSET_MIN: 0,
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
    assert get_schema_suggested_value(schema, "name") == "My tod"
    assert get_schema_suggested_value(schema, CONF_AFTER_KIND) == KIND_FIXED
    assert get_schema_suggested_value(schema, CONF_BEFORE_KIND) == KIND_FIXED

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "My tod",
            CONF_AFTER_KIND: KIND_FIXED,
            CONF_BEFORE_KIND: KIND_FIXED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == AFTER_FIXED

    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_AFTER_TIME) == "10:00"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AFTER_TIME: "10:00"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == BEFORE_FIXED

    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_BEFORE_TIME) == "18:05"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_BEFORE_TIME: "17:05"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "My tod",
        CONF_AFTER_KIND: KIND_FIXED,
        CONF_AFTER_TIME: "10:00",
        CONF_AFTER_OFFSET_MIN: 0,
        CONF_BEFORE_KIND: KIND_FIXED,
        CONF_BEFORE_TIME: "17:05",
        CONF_BEFORE_OFFSET_MIN: 0,
    }

    assert config_entry.data == {}
    assert config_entry.options == result["data"]
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


@pytest.mark.parametrize("platform", ["sensor"])
async def test_config_flow_create_fixed_times(hass: HomeAssistant, platform) -> None:
    """Test create flow with both sides set to fixed times."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "My tod",
            CONF_AFTER_KIND: KIND_FIXED,
            CONF_BEFORE_KIND: KIND_FIXED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == AFTER_FIXED

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_AFTER_TIME: "10:00",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == BEFORE_FIXED

    with patch(
        "homeassistant.components.tod.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BEFORE_TIME: "18:00",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My tod"
    assert result["data"] == {}

    assert result["options"] == {
        "name": "My tod",
        CONF_AFTER_KIND: KIND_FIXED,
        CONF_AFTER_TIME: "10:00",
        CONF_AFTER_OFFSET_MIN: 0,
        CONF_BEFORE_KIND: KIND_FIXED,
        CONF_BEFORE_TIME: "18:00",
        CONF_BEFORE_OFFSET_MIN: 0,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == result["options"]
    assert config_entry.title == "My tod"


@pytest.mark.freeze_time("2022-03-16 17:37:00", tz_offset=-7)
async def test_options_flow_fixed_to_fixed(hass: HomeAssistant) -> None:
    """Test reconfiguring via options; same multi-step flow as create."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My tod",
            CONF_AFTER_KIND: KIND_FIXED,
            CONF_AFTER_TIME: "10:00",
            CONF_AFTER_OFFSET_MIN: 0,
            CONF_BEFORE_KIND: KIND_FIXED,
            CONF_BEFORE_TIME: "18:05",
            CONF_BEFORE_OFFSET_MIN: 0,
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
    assert get_schema_suggested_value(schema, "name") == "My tod"
    assert get_schema_suggested_value(schema, CONF_AFTER_KIND) == KIND_FIXED
    assert get_schema_suggested_value(schema, CONF_BEFORE_KIND) == KIND_FIXED

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "My tod",
            CONF_AFTER_KIND: KIND_FIXED,
            CONF_BEFORE_KIND: KIND_FIXED,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == AFTER_FIXED

    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_AFTER_TIME) == "10:00"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AFTER_TIME: "10:00"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == BEFORE_FIXED

    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_BEFORE_TIME) == "18:05"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_BEFORE_TIME: "17:05"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "My tod",
        CONF_AFTER_KIND: KIND_FIXED,
        CONF_AFTER_TIME: "10:00",
        CONF_AFTER_OFFSET_MIN: 0,
        CONF_BEFORE_KIND: KIND_FIXED,
        CONF_BEFORE_TIME: "17:05",
        CONF_BEFORE_OFFSET_MIN: 0,
    }

    assert config_entry.data == {}
    assert config_entry.options == result["data"]
    assert config_entry.title == "My tod"

    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    state = hass.states.get("binary_sensor.my_tod")
    assert state.state == "off"
    assert state.attributes["after"] == "2022-03-16T10:00:00-07:00"
    assert state.attributes["before"] == "2022-03-16T17:05:00-07:00"
