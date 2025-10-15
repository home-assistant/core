"""Test the Derivative config flow."""

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant import config_entries
from homeassistant.components.derivative.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, get_schema_suggested_value


@pytest.mark.parametrize("platform", ["sensor"])
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    input_sensor_entity_id = "sensor.input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.derivative.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My derivative",
                "round": 1,
                "source": input_sensor_entity_id,
                "time_window": {"seconds": 0},
                "unit_time": "min",
                "max_sub_interval": {"minutes": 1},
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My derivative"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My derivative",
        "round": 1.0,
        "source": "sensor.input",
        "time_window": {"seconds": 0.0},
        "unit_time": "min",
        "max_sub_interval": {"minutes": 1.0},
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My derivative",
        "round": 1.0,
        "source": "sensor.input",
        "time_window": {"seconds": 0.0},
        "unit_time": "min",
        "max_sub_interval": {"minutes": 1.0},
    }
    assert config_entry.title == "My derivative"


@pytest.mark.parametrize("platform", ["sensor"])
@pytest.mark.parametrize(
    ("unit_prefix_entry", "unit_prefix_used"),
    [("k", "k"), ("\u00b5", "\u03bc"), ("\u03bc", "\u03bc")],
)
async def test_options(
    hass: HomeAssistant, platform, unit_prefix_entry: str, unit_prefix_used: str
) -> None:
    """Test reconfiguring and migrated unit prefix."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": "sensor.input",
            "time_window": {"seconds": 0.0},
            "unit_prefix": unit_prefix_entry,
            "unit_time": "min",
            "max_sub_interval": {"seconds": 30},
        },
        title="My derivative",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.input", 10, {"unit_of_measurement": "dog"})
    hass.states.async_set("sensor.valid", 10, {"unit_of_measurement": "dog"})
    hass.states.async_set("sensor.invalid", 10, {"unit_of_measurement": "cat"})

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, "round") == 1.0
    assert get_schema_suggested_value(schema, "time_window") == {"seconds": 0.0}
    assert get_schema_suggested_value(schema, "unit_prefix") == unit_prefix_used
    assert get_schema_suggested_value(schema, "unit_time") == "min"

    source = schema["source"]
    assert isinstance(source, selector.EntitySelector)
    assert source.config["include_entities"] == [
        "sensor.input",
        "sensor.valid",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "source": "sensor.valid",
            "round": 2.0,
            "time_window": {"seconds": 10.0},
            "unit_time": "h",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "My derivative",
        "round": 2.0,
        "source": "sensor.valid",
        "time_window": {"seconds": 10.0},
        "unit_time": "h",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My derivative",
        "round": 2.0,
        "source": "sensor.valid",
        "time_window": {"seconds": 10.0},
        "unit_time": "h",
    }
    assert config_entry.title == "My derivative"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 4

    # Check the state of the entity has changed as expected
    hass.states.async_set("sensor.valid", 10, {"unit_of_measurement": "cat"})
    hass.states.async_set("sensor.valid", 11, {"unit_of_measurement": "cat"})
    await hass.async_block_till_done()
    state = hass.states.get(f"{platform}.my_derivative")
    assert state.attributes["unit_of_measurement"] == "cat/h"


async def test_update_unit(hass: HomeAssistant) -> None:
    """Test behavior of changing the unit_time option."""
    # Setup the config entry
    source_id = "sensor.source"
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": source_id,
            "unit_time": "min",
            "time_window": {"seconds": 0.0},
        },
        title="My derivative",
    )
    derivative_id = "sensor.my_derivative"
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(derivative_id)
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get("unit_of_measurement") is None

    time = dt_util.utcnow()
    with freeze_time(time) as freezer:
        # First state update of the source.
        # Derivative does not learn the unit yet.
        hass.states.async_set(source_id, 5, {"unit_of_measurement": "dogs"})
        await hass.async_block_till_done()
        state = hass.states.get(derivative_id)
        assert state.state == "0.0"
        assert state.attributes.get("unit_of_measurement") is None

        # Second state update of the source.
        time += timedelta(minutes=1)
        freezer.move_to(time)
        hass.states.async_set(source_id, "7", {"unit_of_measurement": "dogs"})
        await hass.async_block_till_done()
        state = hass.states.get(derivative_id)
        assert state.state == "2.0"
        assert state.attributes.get("unit_of_measurement") == "dogs/min"

        # Update the unit_time from minutes to seconds.
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "source": source_id,
                "round": 1.0,
                "unit_time": "s",
                "time_window": {"seconds": 0.0},
            },
        )
        await hass.async_block_till_done()

        # Check the state after reconfigure. Neither unit or state has changed.
        state = hass.states.get(derivative_id)
        assert state.state == "2.0"
        assert state.attributes.get("unit_of_measurement") == "dogs/min"

        # Third state update of the source.
        time += timedelta(seconds=1)
        freezer.move_to(time)
        hass.states.async_set(source_id, "10", {"unit_of_measurement": "dogs"})
        await hass.async_block_till_done()
        state = hass.states.get(derivative_id)
        assert state.state == "3.0"
        # While the state is correctly reporting a state of 3 dogs per second, it incorrectly keeps
        # the unit as dogs/min
        assert state.attributes.get("unit_of_measurement") == "dogs/min"

        # Fourth state update of the source.
        time += timedelta(seconds=1)
        freezer.move_to(time)
        hass.states.async_set(source_id, "20", {"unit_of_measurement": "dogs"})
        await hass.async_block_till_done()
        state = hass.states.get(derivative_id)
        assert state.state == "10.0"
        assert state.attributes.get("unit_of_measurement") == "dogs/min"
