"""Migration functions for KNX config store schema."""

from typing import Any

from homeassistant.const import Platform

from . import const as store_const


def migrate_1_to_2(data: dict[str, Any]) -> None:
    """Migrate from schema 1 to schema 2."""
    if lights := data.get("entities", {}).get(Platform.LIGHT):
        for light in lights.values():
            _migrate_light_schema_1_to_2(light["knx"])


def _migrate_light_schema_1_to_2(light_knx_data: dict[str, Any]) -> None:
    """Migrate light color mode schema."""
    # Remove no more needed helper data from schema
    light_knx_data.pop("_light_color_mode_schema", None)

    # Move color related group addresses to new "color" key
    color: dict[str, Any] = {}
    for color_key in (
        # optional / required and exclusive keys are the same in old and new schema
        store_const.CONF_GA_COLOR,
        store_const.CONF_GA_HUE,
        store_const.CONF_GA_SATURATION,
        store_const.CONF_GA_RED_BRIGHTNESS,
        store_const.CONF_GA_RED_SWITCH,
        store_const.CONF_GA_GREEN_BRIGHTNESS,
        store_const.CONF_GA_GREEN_SWITCH,
        store_const.CONF_GA_BLUE_BRIGHTNESS,
        store_const.CONF_GA_BLUE_SWITCH,
        store_const.CONF_GA_WHITE_BRIGHTNESS,
        store_const.CONF_GA_WHITE_SWITCH,
    ):
        if color_key in light_knx_data:
            color[color_key] = light_knx_data.pop(color_key)

    if color:
        light_knx_data[store_const.CONF_COLOR] = color
