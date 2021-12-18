"""Provides data updates from the Control4 controller for platforms."""
import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DIRECTOR, DOMAIN


async def director_get_entry_variables(
    hass: HomeAssistant, entry: ConfigEntry, item_id: int
) -> dict:
    """Retrieve variable data for Control4 entity."""
    director = hass.data[DOMAIN][entry.entry_id][CONF_DIRECTOR]
    data = await director.getItemVariables(item_id)

    result = {}
    for item in json.loads(data):
        result[item["varName"]] = item["value"]

    return result
