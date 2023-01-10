"""ISY utils."""
from __future__ import annotations

from pyisy.constants import PROTO_INSTEON, PROTO_NETWORK_RESOURCE

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    ISY_CONF_UUID,
    ISY_NET_RES,
    ISY_NODES,
    ISY_PROGRAMS,
    ISY_ROOT,
    ISY_ROOT_NODES,
    ISY_VARIABLES,
    NODE_PLATFORMS,
    PROGRAM_PLATFORMS,
    ROOT_NODE_PLATFORMS,
    VARIABLE_PLATFORMS,
)


def unique_ids_for_config_entry_id(
    hass: HomeAssistant, config_entry_id: str
) -> set[str]:
    """Find all the unique ids for a config entry id."""
    hass_isy_data = hass.data[DOMAIN][config_entry_id]
    uuid = hass_isy_data[ISY_ROOT].configuration[ISY_CONF_UUID]
    current_unique_ids: set[str] = {uuid}

    for platform in NODE_PLATFORMS:
        for node in hass_isy_data[ISY_NODES][platform]:
            current_unique_ids.add(f"{uuid}_{node.address}")

    for platform in PROGRAM_PLATFORMS:
        for _, node, _ in hass_isy_data[ISY_PROGRAMS][platform]:
            current_unique_ids.add(f"{uuid}_{node.address}")

    for platform in VARIABLE_PLATFORMS:
        for node in hass_isy_data[ISY_VARIABLES][platform]:
            current_unique_ids.add(f"{uuid}_{node.address}")
            if platform == Platform.NUMBER:
                current_unique_ids.add(f"{uuid}_{node.address}_init")

    for platform in ROOT_NODE_PLATFORMS:
        for node in hass_isy_data[ISY_ROOT_NODES][platform]:
            current_unique_ids.add(f"{uuid}_{node.address}_query")
            if platform == Platform.BUTTON and node.protocol == PROTO_INSTEON:
                current_unique_ids.add(f"{uuid}_{node.address}_beep")

    for node in hass_isy_data[ISY_NET_RES]:
        current_unique_ids.add(f"{uuid}_{PROTO_NETWORK_RESOURCE}_{node.address}")

    return current_unique_ids
