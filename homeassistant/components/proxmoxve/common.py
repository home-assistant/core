"""Common methods for Proxmox VE integration."""

from typing import Any

from homeassistant.const import CONF_USERNAME

from .const import CONF_REALM


def sanitize_userid(data: dict[str, Any]) -> str:
    """Sanitize the user ID."""
    return (
        data[CONF_USERNAME]
        if "@" in data[CONF_USERNAME]
        else f"{data[CONF_USERNAME]}@{data[CONF_REALM]}"
    )
