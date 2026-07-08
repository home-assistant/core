"""Provides data updates from the Control4 controller for platforms."""
import logging
from collections import defaultdict
from collections.abc import Set
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_DIRECTOR, CONF_DIRECTOR_ALL_ITEMS, Control4ConfigEntry

_LOGGER = logging.getLogger(__name__)

DYNALITE_TRIGGER_PROXY = "dynalite_trigger"


def director_has_dynalite_triggers(entry_data: dict[str, Any] | None) -> bool:
    """True if Director inventory includes at least one dynalite_trigger with an id."""
    if not entry_data:
        return False
    all_items = entry_data.get(CONF_DIRECTOR_ALL_ITEMS) or []
    return any(
        item.get("proxy") == DYNALITE_TRIGGER_PROXY and item.get("id")
        for item in all_items
    )


async def director_get_entry_variables(
    hass: HomeAssistant, entry: Control4ConfigEntry, item_id: int
) -> dict:
    """Retrieve variable data for Control4 entity."""
    director = entry.runtime_data[CONF_DIRECTOR]
    data = await director.get_item_variables(item_id)

    result = {}
    for item in data:
        result[item["varName"]] = item["value"]

    return result


async def update_variables_for_config_entry(
    hass: HomeAssistant, entry: Control4ConfigEntry, variable_names: Set[str]
) -> dict[int, dict[str, Any]]:
    """Retrieve data from the Control4 director."""
    director = entry.runtime_data[CONF_DIRECTOR]    data = await director.get_all_item_variable_value(variable_names)
    result_dict: defaultdict[int, dict[str, Any]] = defaultdict(dict)
    for item in data:
        result_dict[item["id"]][item["varName"]] = item["value"]
    return dict(result_dict)


async def director_get_item_properties(
    hass: HomeAssistant, entry: Control4ConfigEntry, item_id: int
) -> dict[str, Any] | None:
    """Retrieve Director properties for a Control4 item (e.g. area/channel for Dynalite)."""
    entry_data = getattr(entry, "runtime_data", None)
    if not entry_data:
        return None
    director = entry_data.get(CONF_DIRECTOR)
    if not director:
        return None
    url = f"{director.base_url}/api/v1/items/{item_id}/properties"
    session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
    headers = {"Authorization": f"Bearer {director.director_bearer_token}"}
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            _LOGGER.debug(
                "Export: properties for item %s returned status %s",
                item_id,
                resp.status,
            )
            return None
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "Export: failed to get properties for item %s: %s",
            item_id,
            err,
        )
        return None