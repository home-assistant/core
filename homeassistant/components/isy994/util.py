"""ISY utils."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    ISY994_ISY,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_VARIABLES,
    PLATFORMS,
    PROGRAM_PLATFORMS,
)


def unique_ids_for_config_entry_id(
    hass: HomeAssistant, config_entry_id: str
) -> set[str]:
    """Find all the unique ids for a config entry id."""
    hass_isy_data = hass.data[DOMAIN][config_entry_id]
    uuid = hass_isy_data[ISY994_ISY].configuration["uuid"]
    current_unique_ids: set[str] = {uuid}

    for platform in PLATFORMS:
        for node in hass_isy_data[ISY994_NODES][platform]:
            if hasattr(node, "address"):
                current_unique_ids.add(f"{uuid}_{node.address}")

    for platform in PROGRAM_PLATFORMS:
        for _, node, _ in hass_isy_data[ISY994_PROGRAMS][platform]:
            if hasattr(node, "address"):
                current_unique_ids.add(f"{uuid}_{node.address}")

    for node in hass_isy_data[ISY994_VARIABLES]:
        if hasattr(node, "address"):
            current_unique_ids.add(f"{uuid}_{node.address}")

    return current_unique_ids
