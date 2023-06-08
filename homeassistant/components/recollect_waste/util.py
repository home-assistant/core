"""Define ReCollect Waste utilities."""
from aiorecollect.client import PickupType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME
from homeassistant.core import callback


@callback
def async_get_pickup_type_names(
    entry: ConfigEntry, pickup_types: list[PickupType]
) -> list[str]:
    """Return proper pickup type names from their associated objects."""
    return [
        t.friendly_name
        if entry.options.get(CONF_FRIENDLY_NAME) and t.friendly_name
        else t.name
        for t in pickup_types
    ]
