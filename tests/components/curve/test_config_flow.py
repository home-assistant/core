"""Test the Curve config flow."""

import json
from typing import Any

import pytest

from homeassistant import config_entries
from homeassistant.components.curve.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_SEGMENTS, MOCK_STEP_SEGMENTS

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.parametrize(
    "with_source",
    [True, False],
    ids=["with_source", "without_source"],
)
async def test_user_flow_success(hass: HomeAssistant, with_source: bool) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    config: dict[str, Any] = {
        "name": "Test Curve",
        "segments": json.dumps(MOCK_SEGMENTS),
    }
    if with_source:
        config["source"] = "sensor.test_source"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Curve"
    opts = result["options"]
    assert opts["name"] == "Test Curve"
    assert opts.get("source") == ("sensor.test_source" if with_source else None)
    segs = opts["segments"]
    assert len(segs) == 2
    # Segments will have type field added (defaults to "linear") and values as floats
    assert segs[0]["x0"] == 0.0
    assert segs[0]["type"] == "linear"


arg_tests = [
    pytest.param({"segments": "invalid json {"}, "invalid_segments_json"),
    pytest.param({"segments": "[]"}, "no_segments"),
    pytest.param({"segments": "8"}, "invalid_segments_json"),
    pytest.param({"segments": "[8]"}, "invalid_segment_structure"),
    pytest.param({"segments": "[[8]]"}, "invalid_segment_structure"),  # short shorthand
    pytest.param({"segments": '[{"x0": 0, "y0": 0}]'}, "invalid_segment_structure"),
    pytest.param(
        {"segments": '[{"x0": "abc", "y0": 0, "x1": 10, "y1": 5}]'},
        "invalid_segment_values",
    ),
    pytest.param(
        {"segments": '[{"x0": 0, "y0": 0, "x1": 10, "y1": 5, "type": "invalid_type"}]'},
        "invalid_interpolation_type",
    ),
]


@pytest.mark.parametrize(("args", "error"), arg_tests)
async def test_user_flow_invalid(
    hass: HomeAssistant, args: dict[str, Any], error: str
) -> None:
    """Test user flow with invalid values."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Test Curve",
            "source": "sensor.test_source",
            **args,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_segments = MOCK_STEP_SEGMENTS

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "source": "sensor.new_source",
            "segments": json.dumps(new_segments),
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options["source"] == "sensor.new_source"
    assert mock_config_entry.options["segments"] == new_segments
