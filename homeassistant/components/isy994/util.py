"""ISY utils."""
from __future__ import annotations

from pyisy.constants import PROP_COMMS_ERROR, PROTO_INSTEON

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_NETWORK,
    DOMAIN,
    ISY_NET_RES,
    ISY_NODES,
    ISY_PROGRAMS,
    ISY_ROOT,
    ISY_ROOT_NODES,
    ISY_VARIABLES,
    NODE_PLATFORMS,
    PROGRAM_PLATFORMS,
    ROOT_NODE_PLATFORMS,
    SENSOR_AUX,
)


def unique_ids_for_config_entry_id(
    hass: HomeAssistant, config_entry_id: str
) -> set[tuple[Platform | str, str]]:
    """Find all the unique ids for a config entry id."""
    hass_isy_data = hass.data[DOMAIN][config_entry_id]
    isy = hass_isy_data[ISY_ROOT]
    current_unique_ids: set[tuple[Platform | str, str]] = {
        (Platform.BUTTON, f"{isy.uuid}_query")
    }

    # Structure and prefixes here must match what's added in __init__ and helpers
    for platform in NODE_PLATFORMS:
        for node in hass_isy_data[ISY_NODES][platform]:
            current_unique_ids.add((platform, f"{isy.uuid}_{node.address}"))

    for node, control in hass_isy_data[ISY_NODES][SENSOR_AUX]:
        current_unique_ids.add(
            (Platform.SENSOR, f"{isy.uuid}_{node.address}_{control}")
        )
        current_unique_ids.add(
            (Platform.SENSOR, f"{isy.uuid}_{node.address}_{PROP_COMMS_ERROR}")
        )

    for platform in PROGRAM_PLATFORMS:
        for _, node, _ in hass_isy_data[ISY_PROGRAMS][platform]:
            current_unique_ids.add((platform, f"{isy.uuid}_{node.address}"))

    for node, _ in hass_isy_data[ISY_VARIABLES][Platform.NUMBER]:
        current_unique_ids.add((Platform.NUMBER, f"{isy.uuid}_{node.address}"))
        current_unique_ids.add((Platform.NUMBER, f"{isy.uuid}_{node.address}_init"))
    for _, node in hass_isy_data[ISY_VARIABLES][Platform.SENSOR]:
        current_unique_ids.add((Platform.SENSOR, f"{isy.uuid}_{node.address}"))

    for platform in ROOT_NODE_PLATFORMS:
        for node in hass_isy_data[ISY_ROOT_NODES][platform]:
            current_unique_ids.add((platform, f"{isy.uuid}_{node.address}_query"))
            if platform == Platform.BUTTON and node.protocol == PROTO_INSTEON:
                current_unique_ids.add((platform, f"{isy.uuid}_{node.address}_beep"))

    for node in hass_isy_data[ISY_NET_RES]:
        current_unique_ids.add(
            (Platform.BUTTON, f"{isy.uuid}_{CONF_NETWORK}_{node.address}")
        )

    return current_unique_ids
