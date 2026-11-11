"""Test the Times of the Day config flow."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.tod.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData


async def test_form(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the transition selector offered by the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["data_schema"].schema["after"].serialize() == snapshot


@pytest.mark.parametrize(
    ("after", "before"),
    [
        pytest.param(
            {"active_choice": "time", "time": "10:00"},
            {"active_choice": "time", "time": "18:00"},
            id="time",
        ),
        pytest.param(
            {
                "active_choice": "sun",
                "sun": {"event": "sunrise", "offset": {"hours": -2}},
            },
            {
                "active_choice": "sun",
                "sun": {"event": "sunset", "offset": {"minutes": 30}},
            },
            id="sun",
        ),
        pytest.param(
            {"active_choice": "sun", "sun": {"event": "sunrise"}},
            {"active_choice": "time", "time": "07:00"},
            id="sun-to-time",
        ),
        pytest.param(
            {"active_choice": "time", "time": "17:00"},
            {"active_choice": "sun", "sun": {"event": "sunset"}},
            id="time-to-sun",
        ),
    ],
)
async def test_config_flow(
    hass: HomeAssistant,
    after: dict[str, Any],
    before: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating fixed time, sun, and mixed transitions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.tod.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"after": after, "before": before, "name": "My tod"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My tod"
    assert result["data"] == {}
    assert result["options"] == snapshot
    mock_setup_entry.assert_called_once()

    config_entry = result["result"]
    assert config_entry.data == {}
    assert config_entry.options == result["options"]
    assert config_entry.title == "My tod"
    assert config_entry.version == 2


@pytest.mark.parametrize(
    "transition",
    [
        pytest.param({"active_choice": "time", "time": "25:00"}, id="invalid-time"),
        pytest.param(
            {
                "active_choice": "time",
                "time": {"time": "10:00", "offset": {"minutes": 30}},
            },
            id="time-offset",
        ),
        pytest.param(
            {"active_choice": "sun", "sun": {"event": "noon"}}, id="invalid-sun"
        ),
        pytest.param(
            {"active_choice": "sun", "sun": {"offset": {"hours": 1}}},
            id="missing-event",
        ),
        pytest.param(
            {
                "active_choice": "sun",
                "sun": {"event": "sunrise", "offset": {"hours": "invalid"}},
            },
            id="invalid-offset",
        ),
    ],
)
async def test_invalid_transition(
    hass: HomeAssistant, transition: dict[str, Any]
) -> None:
    """Test rejecting invalid transitions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My tod",
                "after": transition,
                "before": {"active_choice": "time", "time": "18:00"},
            },
        )


@pytest.mark.freeze_time("2022-03-16 17:37:00", tz_offset=-7)
@pytest.mark.parametrize(
    ("after", "before", "new_before"),
    [
        pytest.param(
            {"time": "10:00"},
            {"time": "18:05"},
            {"active_choice": "time", "time": "17:05"},
            id="time",
        ),
        pytest.param(
            {"event": "sunrise", "offset": {"hours": -2}},
            {"event": "sunset", "offset": {"minutes": 30}},
            {"active_choice": "time", "time": "17:05"},
            id="sun-to-time",
        ),
        pytest.param(
            {"time": "10:00"},
            {"time": "18:05"},
            {
                "active_choice": "sun",
                "sun": {"event": "sunset", "offset": {"hours": -12}},
            },
            id="time-to-sun",
        ),
        pytest.param(
            {"event": "sunrise", "offset": {"hours": -2}},
            {"event": "sunset", "offset": {"minutes": 30}},
            {"active_choice": "sun", "sun": {"event": "sunset"}},
            id="remove-sun-offset",
        ),
        pytest.param(
            {"event": "sunrise", "offset": {"hours": -2}},
            {"time": "12:00"},
            {"active_choice": "time", "time": "13:00"},
            id="mixed-sun-to-time",
        ),
        pytest.param(
            {"time": "12:00"},
            {"event": "sunset", "offset": {"minutes": 30}},
            {"active_choice": "sun", "sun": {"event": "sunset"}},
            id="mixed-time-to-sun",
        ),
    ],
)
async def test_options(
    hass: HomeAssistant,
    after: dict[str, Any],
    before: dict[str, Any],
    new_before: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test reconfiguring transitions and reloading the existing entity."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"after": after, "before": before, "name": "My tod"},
        title="My tod",
        version=2,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    suggested_after = get_schema_suggested_value(schema, "after")
    suggested_before = get_schema_suggested_value(schema, "before")
    after_choice = next(iter(schema["after"].config["choices"]))
    before_choice = next(iter(schema["before"].config["choices"]))
    assert (after_choice, suggested_after, before_choice, suggested_before) == snapshot

    # The frontend wraps suggested values in the first selector choice.
    after_input = {"active_choice": after_choice, after_choice: suggested_after}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"after": after_input, "before": new_before},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == snapshot(name="options")
    assert config_entry.data == {}
    assert config_entry.options == result["data"]
    assert config_entry.title == "My tod"

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1
    state = hass.states.get("binary_sensor.my_tod")
    assert state == snapshot

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert (
        get_schema_suggested_value(result["data_schema"].schema, "after"),
        get_schema_suggested_value(result["data_schema"].schema, "before"),
    ) == snapshot(name="reopened")
