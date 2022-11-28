"""Test the Statistics config flow."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant import config_entries
from homeassistant.components.statistics.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.util.dt as dt_util

from .common import generate_statistics

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "period_type, period_input, period_data",
    (
        (
            "calendar",
            {"calendar_offset": 2, "calendar_period": "day"},
            {"offset": 2, "period": "day"},
        ),
        (
            "fixed_period",
            {
                "fixed_period_end_time": "2022-03-24 00:00",
                "fixed_period_start_time": "2022-03-24 00:00",
            },
            {"end_time": "2022-03-24 00:00", "start_time": "2022-03-24 00:00"},
        ),
        (
            "rolling_window",
            {
                "rolling_window_duration": {"days": 365},
                "rolling_window_offset": {"days": -365},
            },
            {"duration": {"days": 365}, "offset": {"days": -365}},
        ),
    ),
)
async def test_config_flow(
    hass: HomeAssistant, period_type, period_input, period_data
) -> None:
    """Test the config flow."""
    input_sensor = "sensor.input_one"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "My statistics",
            "entity_id": input_sensor,
            "state_characteristic": "value_max_lts",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": period_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == period_type

    with patch(
        "homeassistant.components.statistics.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            period_input,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My statistics"
    assert result["data"] == {}
    assert result["options"] == {
        "entity_id": input_sensor,
        "name": "My statistics",
        "period": {period_type: period_data},
        "precision": 2.0,
        "state_characteristic": "value_max_lts",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": input_sensor,
        "name": "My statistics",
        "period": {period_type: period_data},
        "precision": 2.0,
        "state_characteristic": "value_max_lts",
    }
    assert config_entry.title == "My statistics"


@pytest.mark.parametrize(
    "period_type, period_definition",
    (
        (
            "calendar",
            {"period": "day", "offset": 2},
        ),
        (
            "fixed_period",
            {"start_time": "2022-03-24 00:00", "end_time": "2022-03-24 00:00"},
        ),
        (
            "rolling_window",
            {"duration": {"days": 365}, "offset": {"days": -365}},
        ),
    ),
)
async def test_config_flow_import(
    hass: HomeAssistant, period_type, period_definition
) -> None:
    """Test the config flow."""
    input_sensor = "sensor.input_one"

    with patch(
        "homeassistant.components.statistics.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                "entity": input_sensor,
                "name": "My statistics",
                "period": {period_type: period_definition},
                "precision": 2.0,
                "state_type": "max",
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My statistics"
    assert result["data"] == {}
    assert result["options"] == {
        "entity_id": input_sensor,
        "name": "My statistics",
        "period": {period_type: period_definition},
        "precision": 2.0,
        "state_characteristic": "value_max_lts",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": input_sensor,
        "name": "My statistics",
        "period": {period_type: period_definition},
        "precision": 2.0,
        "state_characteristic": "value_max_lts",
    }
    assert config_entry.title == "My statistics"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@freeze_time(datetime(2022, 10, 21, 7, 25, tzinfo=timezone.utc))
async def test_options(recorder_mock, hass: HomeAssistant) -> None:
    """Test reconfiguring."""

    now = dt_util.utcnow()

    zero = now
    start = zero.replace(minute=0, second=0, microsecond=0) + timedelta(days=-2)

    await generate_statistics(hass, "sensor.input_one", start, 6)
    await generate_statistics(hass, "sensor.input_two", start, 6)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": "sensor.input_one",
            "name": "My statistics",
            "period": {"calendar": {"offset": -2, "period": "day"}},
            "precision": 2.0,
            "state_characteristic": "value_max_lts",
        },
        title="My statistics",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state of the entity is reflecting the initial settings
    state = hass.states.get("sensor.my_statistics")
    assert state.state == "10.0"

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "entity_id") == "sensor.input_one"
    assert get_suggested(schema, "precision") == 2.0
    assert get_suggested(schema, "state_characteristic") == "value_max_lts"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entity_id": "sensor.input_two",
            "precision": 1,
            "state_characteristic": "value_min_lts",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "rolling_window"},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rolling_window"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "rolling_window_duration": {"days": 2},
            "rolling_window_offset": {"hours": -1},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entity_id": "sensor.input_two",
        "name": "My statistics",
        "period": {
            "rolling_window": {"duration": {"days": 2}, "offset": {"hours": -1}}
        },
        "precision": 1.0,
        "state_characteristic": "value_min_lts",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": "sensor.input_two",
        "name": "My statistics",
        "period": {
            "rolling_window": {"duration": {"days": 2}, "offset": {"hours": -1}}
        },
        "precision": 1.0,
        "state_characteristic": "value_min_lts",
    }
    assert config_entry.title == "My statistics"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    # Check the state of the entity has changed as expected
    state = hass.states.get("sensor.my_statistics")
    assert state.state == "-12.0"


@freeze_time(datetime(2022, 10, 21, 7, 25, tzinfo=timezone.utc))
@pytest.mark.parametrize(
    "period_type, period, suggested_values",
    (
        (
            "calendar",
            {"offset": -2, "period": "day"},
            {"calendar_offset": -2, "calendar_period": "day"},
        ),
        (
            "fixed_period",
            {"start_time": "2022-03-24 00:00", "end_time": "2022-03-24 00:00"},
            {},
        ),
        (
            "rolling_window",
            {"duration": {"days": 365}, "offset": {"days": -365}},
            {},
        ),
    ),
)
async def test_options_edit_period(
    recorder_mock, hass: HomeAssistant, period_type, period, suggested_values
) -> None:
    """Test reconfiguring period."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": "sensor.input_one",
            "name": "My statistics",
            "period": {period_type: period},
            "precision": 2.0,
            "state_characteristic": "value_max_lts",
        },
        title="My statistics",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "entity_id") == "sensor.input_one"
    assert get_suggested(schema, "precision") == 2.0
    assert get_suggested(schema, "state_characteristic") == "value_max_lts"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entity_id": "sensor.input_two",
            "precision": 1,
            "state_characteristic": "value_max_lts",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": period_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == period_type

    schema = result["data_schema"].schema
    for key, configured_value in period.items():
        assert get_suggested(schema, f"{period_type}_{key}") == configured_value
