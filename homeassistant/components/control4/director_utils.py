"""Provides data updates from the Control4 controller for platforms."""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
import logging
from typing import Any

from pyControl4.error_handling import BadToken

from homeassistant.core import HomeAssistant

from .const import Control4ConfigEntry

_LOGGER = logging.getLogger(__name__)

_TRUE_STRINGS = {"true", "1"}
_FALSE_STRINGS = {"false", "0"}


def to_bool(value: Any) -> bool | None:
    """Normalize a Control4 boolean-ish variable that may arrive as a string."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_STRINGS:
            return True
        if normalized in _FALSE_STRINGS:
            return False
        return None
    if value is None:
        return None
    return bool(value)


async def _with_token_refresh[T](
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    call: Callable[[], Coroutine[Any, Any, T]],
) -> T:
    """Call `call`, refreshing the director token once on BadToken."""
    try:
        return await call()
    except BadToken:
        pass

    async with entry.runtime_data.token_refresh_lock:
        try:
            return await call()
        except BadToken:
            _LOGGER.debug("Updating Control4 director token")
            from . import refresh_tokens  # noqa: PLC0415

            await refresh_tokens(hass, entry)

    return await call()


async def _get_entry_variables(entry: Control4ConfigEntry, item_id: int) -> dict:
    director = entry.runtime_data.director
    data = await director.get_item_variables(item_id)

    result = {}
    for item in data:
        value = item["value"]
        result[item["varName"]] = None if value == "Undefined" else value

    return result


async def director_get_entry_variables(
    hass: HomeAssistant, entry: Control4ConfigEntry, item_id: int
) -> dict:
    """Retrieve variable data for Control4 entity."""
    return await _with_token_refresh(
        hass, entry, lambda: _get_entry_variables(entry, item_id)
    )


async def gather_entry_variables(
    hass: HomeAssistant, entry: Control4ConfigEntry, item_ids: list[int]
) -> dict[int, dict]:
    """Retrieve variable data for multiple Control4 entities concurrently."""
    results = await asyncio.gather(
        *(director_get_entry_variables(hass, entry, item_id) for item_id in item_ids),
        return_exceptions=True,
    )
    variables_by_id: dict[int, dict] = {}
    for item_id, result in zip(item_ids, results, strict=True):
        if isinstance(result, BaseException):
            _LOGGER.warning(
                "Failed to fetch initial variables for item %s: %s", item_id, result
            )
            variables_by_id[item_id] = {}
        else:
            variables_by_id[item_id] = result
    return variables_by_id


async def _update_variables_for_config_entry(
    entry: Control4ConfigEntry, variable_names: set[str]
) -> dict[int, dict[str, Any]]:
    director = entry.runtime_data.director
    data = await director.get_all_item_variable_value(variable_names)
    result_dict: defaultdict[int, dict[str, Any]] = defaultdict(dict)
    for item in data:
        result_dict[item["id"]][item["varName"]] = item["value"]
    return dict(result_dict)


async def update_variables_for_config_entry(
    hass: HomeAssistant, entry: Control4ConfigEntry, variable_names: set[str]
) -> dict[int, dict[str, Any]]:
    """Retrieve data from the Control4 director."""
    return await _with_token_refresh(
        hass, entry, lambda: _update_variables_for_config_entry(entry, variable_names)
    )
