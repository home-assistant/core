"""Test the Times of the Day config flow."""

from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.tod.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, section

from tests.common import MockConfigEntry, get_schema_suggested_value


def _section_schema(schema: vol.Schema, section_key: str) -> dict[vol.Marker, Any]:
    """Return the schema nested in a form section."""
    section_value = next(
        value for key, value in schema.schema.items() if key.schema == section_key
    )
    assert isinstance(section_value, section)
    return section_value.schema.schema


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow with specific times."""
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
                "after": {
                    "offset": {"minutes": -30},
                    "time": "10:00",
                },
                "before": {
                    "offset": {"hours": 1},
                    "time": "18:00",
                },
                "name": "My tod",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My tod"
    assert result["data"] == {}
    assert result["options"] == {
        "after_offset": {"minutes": -30},
        "after_time": "10:00",
        "before_offset": {"hours": 1},
        "before_time": "18:00",
        "name": "My tod",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_sun_events(hass: HomeAssistant) -> None:
    """Test the config flow with sun events."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tod.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "after": {
                    "offset": {"minutes": -30},
                    "sun_event": "sunrise",
                },
                "before": {
                    "offset": {"minutes": 30},
                    "sun_event": "sunset",
                },
                "name": "Daytime",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        "after_offset": {"minutes": -30},
        "after_time": "sunrise",
        "before_offset": {"minutes": 30},
        "before_time": "sunset",
        "name": "Daytime",
    }


@pytest.mark.parametrize(
    ("after", "error"),
    [
        pytest.param({}, "after_one_value", id="neither"),
        pytest.param(
            {"sun_event": "sunrise", "time": "10:00"},
            "after_one_value",
            id="both",
        ),
    ],
)
async def test_config_flow_requires_one_boundary_value(
    hass: HomeAssistant, after: dict[str, Any], error: str
) -> None:
    """Test exactly one value is required for each boundary."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "after": after,
            "before": {"time": "18:00"},
            "name": "My tod",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize(
    "offset",
    [
        pytest.param({"days": 1}, id="positive"),
        pytest.param({"hours": -24}, id="negative"),
    ],
)
async def test_config_flow_rejects_multi_day_offset(
    hass: HomeAssistant, offset: dict[str, float]
) -> None:
    """Test offsets must be less than one day."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "after": {"offset": offset, "time": "10:00"},
            "before": {"time": "18:00"},
            "name": "My tod",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "after_offset_range"}


@pytest.mark.freeze_time("2022-03-16 17:37:00", tz_offset=-7)
async def test_options_time_boundaries(hass: HomeAssistant) -> None:
    """Test reconfiguring specific-time boundaries."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "after_offset": {"minutes": 30},
            "after_time": "10:00",
            "before_offset": {"minutes": 5},
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
    after_schema = _section_schema(result["data_schema"], "after")
    before_schema = _section_schema(result["data_schema"], "before")
    assert [key.schema for key in after_schema] == ["time", "offset"]
    assert [key.schema for key in before_schema] == ["time", "offset"]
    assert get_schema_suggested_value(after_schema, "time") == "10:00"
    assert get_schema_suggested_value(after_schema, "offset") == {"minutes": 30}
    assert get_schema_suggested_value(before_schema, "time") == "18:05"
    assert get_schema_suggested_value(before_schema, "offset") == {"minutes": 5}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "after": {"time": "10:00"},
            "before": {"offset": {"minutes": -5}, "time": "17:05"},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "after_time": "10:00",
        "before_offset": {"minutes": -5},
        "before_time": "17:05",
        "name": "My tod",
    }

    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.my_tod")
    assert state.state == "off"
    assert state.attributes["after"] == "2022-03-16T10:00:00-07:00"
    assert state.attributes["before"] == "2022-03-16T17:00:00-07:00"


async def test_options_sun_event_boundaries(hass: HomeAssistant) -> None:
    """Test options preserve solar boundary types."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "after_offset": {"minutes": -30},
            "after_time": "sunrise",
            "before_offset": {"minutes": 30},
            "before_time": "sunset",
            "name": "Daytime",
        },
        title="Daytime",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    after_schema = _section_schema(result["data_schema"], "after")
    before_schema = _section_schema(result["data_schema"], "before")
    assert [key.schema for key in after_schema] == ["sun_event", "offset"]
    assert [key.schema for key in before_schema] == ["sun_event", "offset"]
    assert get_schema_suggested_value(after_schema, "sun_event") == "sunrise"
    assert get_schema_suggested_value(before_schema, "sun_event") == "sunset"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "after": {"offset": {"minutes": -15}, "sun_event": "sunset"},
            "before": {"offset": {"minutes": 15}, "sun_event": "sunrise"},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "after_offset": {"minutes": -15},
        "after_time": "sunset",
        "before_offset": {"minutes": 15},
        "before_time": "sunrise",
        "name": "Daytime",
    }
