"""Helper functions for swiss_public_transport."""

from types import MappingProxyType
from typing import Any

from .const import CONF_DESTINATION, CONF_START, CONF_VIA


def unique_id_from_config(config: MappingProxyType[str, Any] | dict[str, Any]) -> str:
    """Build a unique id from a config entry."""
    return f"{config[CONF_START]} {config[CONF_DESTINATION]}" + (
        " via " + ", ".join(config[CONF_VIA])
        if CONF_VIA in config and len(config[CONF_VIA]) > 0
        else ""
    )
