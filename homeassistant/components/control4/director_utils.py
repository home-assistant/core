"""Provides data updates from the Control4 controller for platforms."""

from collections import defaultdict
from collections.abc import Set as AbstractSet
import logging
from typing import Any

from pyControl4.error_handling import BadToken

from homeassistant.core import HomeAssistant

from .const import CONF_DIRECTOR, Control4ConfigEntry

_LOGGER = logging.getLogger(__name__)


async def _get_entry_variables(entry: Control4ConfigEntry, item_id: int) -> dict:
    director = entry.runtime_data[CONF_DIRECTOR]
    data = await director.get_item_variables(item_id)

    result = {}
    for item in data:
        result[item["varName"]] = item["value"]

    return result


async def director_get_entry_variables(
    hass: HomeAssistant, entry: Control4ConfigEntry, item_id: int
) -> dict:
    """Retrieve variable data for Control4 entity."""
    try:
        return await _get_entry_variables(entry, item_id)
    except BadToken:
        _LOGGER.debug("Updating Control4 director token")
        from . import refresh_tokens  # noqa: PLC0415

        await refresh_tokens(hass, entry)
        return await _get_entry_variables(entry, item_id)


async def _update_variables_for_config_entry(
    entry: Control4ConfigEntry, variable_names: AbstractSet[str]
) -> dict[int, dict[str, Any]]:
    director = entry.runtime_data[CONF_DIRECTOR]
    data = await director.get_all_item_variable_value(variable_names)
    result_dict: defaultdict[int, dict[str, Any]] = defaultdict(dict)
    for item in data:
        result_dict[item["id"]][item["varName"]] = item["value"]
    return dict(result_dict)


async def update_variables_for_config_entry(
    hass: HomeAssistant, entry: Control4ConfigEntry, variable_names: AbstractSet[str]
) -> dict[int, dict[str, Any]]:
    """Retrieve data from the Control4 director."""
    try:
        return await _update_variables_for_config_entry(entry, variable_names)
    except BadToken:
        _LOGGER.debug("Updating Control4 director token")
        from . import refresh_tokens  # noqa: PLC0415

        await refresh_tokens(hass, entry)
        return await _update_variables_for_config_entry(entry, variable_names)
