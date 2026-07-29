"""Config flow tests for the Color helper."""

from typing import Any

import pytest

from homeassistant.components.color.config_flow import _coerce_color_input
from homeassistant.components.color.const import (
    CONF_INITIAL_BRIGHTNESS,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_KELVIN,
    CONF_INITIAL_MODE,
    DEFAULT_HEX,
    DOMAIN,
    MODE_CHROMATIC,
    MODE_WHITE,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ICON, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_flow_chromatic_path(hass: HomeAssistant) -> None:
    """Test creating a chromatic color via the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Living Room Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "chromatic"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INITIAL_COLOR: [255, 128, 0]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room Color"
    assert result["data"][CONF_INITIAL_COLOR] == "#FF8000"
    assert CONF_INITIAL_BRIGHTNESS not in result["data"]


async def test_flow_white_path(hass: HomeAssistant) -> None:
    """Test creating a white (color temperature) color via the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Warm White",
            CONF_INITIAL_MODE: MODE_WHITE,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "white"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INITIAL_KELVIN: 2700, CONF_INITIAL_BRIGHTNESS: 150},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_INITIAL_KELVIN] == 2700
    assert result["data"][CONF_INITIAL_MODE] == MODE_WHITE
    assert result["data"][CONF_INITIAL_BRIGHTNESS] == 150


async def test_options_flow_updates_icon(hass: HomeAssistant) -> None:
    """Test the options flow updates the icon."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Icon Test",
        data={
            CONF_NAME: "Icon Test",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FFFFFF",
            CONF_ICON: "mdi:palette",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ICON: "mdi:lightbulb"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ICON] == "mdi:lightbulb"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("#ABCDEF", "#ABCDEF", id="string-passthrough"),
        pytest.param([255, 128, 0], "#FF8000", id="rgb-list"),
        pytest.param((0, 255, 0), "#00FF00", id="rgb-tuple"),
        pytest.param({"r": 1, "g": 2, "b": 3}, DEFAULT_HEX, id="dict-falls-back"),
        pytest.param([1, 2, 3, 4], DEFAULT_HEX, id="wrong-length-falls-back"),
        pytest.param(None, DEFAULT_HEX, id="none-falls-back"),
    ],
)
def test_coerce_color_input(raw: Any, expected: str) -> None:
    """Test coercion of ColorRGBSelector results to hex strings."""
    assert _coerce_color_input(raw) == expected
