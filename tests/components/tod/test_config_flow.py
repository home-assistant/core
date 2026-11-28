"""Test the Times of the Day config flow."""

from typing import Any
from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.tod.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    FlowResultType,
    InvalidData,
    add_visible_conditions_to_serialized_schema,
)
from homeassistant.helpers import config_validation as cv

FORM_FIELDS = (
    "after",
    "after_time",
    "after_sun",
    "after_offset",
    "before",
    "before_time",
    "before_sun",
    "before_offset",
)


async def test_form(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the selectors and visibility conditions offered by the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    schema = result["data_schema"]
    fields = probatio.to_field_list(schema, custom_serializer=cv.custom_serializer)
    add_visible_conditions_to_serialized_schema(schema, fields)
    assert fields == snapshot


@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(
            {
                "after": "time",
                "after_time": "10:00",
                "before": "time",
                "before_time": "18:00",
            },
            id="time",
        ),
        pytest.param(
            {"after_time": "10:00", "before_time": "18:00"},
            id="default-time",
        ),
        pytest.param(
            {
                "after": "sun",
                "after_sun": "sunrise",
                "after_offset": {"hours": -2},
                "before": "sun",
                "before_sun": "sunset",
                "before_offset": {"minutes": 30},
            },
            id="sun",
        ),
        pytest.param(
            {
                "after": "sun",
                "after_sun": "sunrise",
                "before": "time",
                "before_time": "07:00",
            },
            id="sun-to-time",
        ),
        pytest.param(
            {
                "after": "time",
                "after_time": "17:00",
                "before": "sun",
                "before_sun": "sunset",
            },
            id="time-to-sun",
        ),
        pytest.param(
            {
                "after": "time",
                "after_time": "10:00",
                "after_sun": "invalid",
                "after_offset": {"minutes": "invalid"},
                "before": "time",
                "before_time": "18:00",
                "before_sun": "invalid",
                "before_offset": {"minutes": "invalid"},
            },
            id="hidden-sun-fields",
        ),
        pytest.param(
            {
                "after": "sun",
                "after_sun": "sunrise",
                "after_time": "invalid",
                "before": "sun",
                "before_sun": "sunset",
                "before_time": "invalid",
            },
            id="hidden-time-fields",
        ),
    ],
)
async def test_config_flow(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test creating fixed time, sun, and mixed boundaries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.tod.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "My tod", **user_input}
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
    "user_input",
    [
        pytest.param({"after": "time", "after_time": "25:00"}, id="invalid-time"),
        pytest.param({"after": "time"}, id="missing-time"),
        pytest.param({"after": "sun", "after_sun": "noon"}, id="invalid-sun"),
        pytest.param({"after": "sun"}, id="missing-sun"),
        pytest.param({"after": "invalid"}, id="invalid-type"),
        pytest.param(
            {
                "after": "sun",
                "after_sun": "sunrise",
                "after_offset": {"hours": "invalid"},
            },
            id="invalid-offset",
        ),
    ],
)
async def test_invalid_boundary(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> None:
    """Test rejecting missing or invalid visible fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My tod",
                "before": "time",
                "before_time": "18:00",
                **user_input,
            },
        )


@pytest.mark.freeze_time("2022-03-16 17:37:00", tz_offset=-7)
@pytest.mark.parametrize(
    ("after", "before", "user_input"),
    [
        pytest.param(
            {"time": "10:00"},
            {"time": "18:05"},
            {
                "after": "time",
                "after_time": "10:00",
                "before": "time",
                "before_time": "17:05",
            },
            id="time",
        ),
        pytest.param(
            {"event": "sunrise", "offset": {"hours": -2}},
            {"event": "sunset", "offset": {"minutes": 30}},
            {
                "after": "sun",
                "after_sun": "sunrise",
                "after_offset": {"hours": -2},
                "before": "time",
                "before_time": "17:05",
                "before_sun": "sunset",
                "before_offset": {"minutes": 30},
            },
            id="sun-to-time",
        ),
        pytest.param(
            {"time": "10:00"},
            {"time": "18:05"},
            {
                "after": "time",
                "after_time": "10:00",
                "before": "sun",
                "before_sun": "sunset",
                "before_offset": {"hours": -12},
                "before_time": "18:05",
            },
            id="time-to-sun",
        ),
        pytest.param(
            {"event": "sunrise", "offset": {"hours": -2}},
            {"event": "sunset", "offset": {"minutes": 30}},
            {
                "after": "sun",
                "after_sun": "sunrise",
                "after_offset": {"hours": -2},
                "before": "sun",
                "before_sun": "sunset",
            },
            id="remove-sun-offset",
        ),
        pytest.param(
            {"event": "sunrise", "offset": {"hours": -2}},
            {"time": "12:00"},
            {
                "after": "sun",
                "after_sun": "sunrise",
                "after_offset": {"hours": -2},
                "before": "time",
                "before_time": "13:00",
            },
            id="mixed-sun-to-time",
        ),
        pytest.param(
            {"time": "12:00"},
            {"event": "sunset", "offset": {"minutes": 30}},
            {
                "after": "time",
                "after_time": "12:00",
                "before": "sun",
                "before_sun": "sunset",
            },
            id="mixed-time-to-sun",
        ),
    ],
)
async def test_options(
    hass: HomeAssistant,
    after: dict[str, Any],
    before: dict[str, Any],
    user_input: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test restoring values, changing modes, and reloading the same entity."""
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
    assert (
        tuple(
            get_schema_suggested_value(result["data_schema"].schema, key)
            for key in FORM_FIELDS
        )
        == snapshot
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == snapshot(name="options")
    assert config_entry.data == {}
    assert config_entry.options == result["data"]
    assert config_entry.title == "My tod"

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("binary_sensor.my_tod") == snapshot

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert tuple(
        get_schema_suggested_value(result["data_schema"].schema, key)
        for key in FORM_FIELDS
    ) == snapshot(name="reopened")
