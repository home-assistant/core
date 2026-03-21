"""Common methods for Proxmox VE integration."""

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_AUTH_PROVIDERS, CONF_USERNAME

from .const import CONF_REALM


def sanitize_config_entry(input_data: Mapping[str, Any]) -> dict[str, Any]:
    """Sanitize the user ID and realm in config_entry data."""
    data = dict(input_data)
    username = data[CONF_USERNAME].split("@")[0]
    realm = (
        data[CONF_REALM].lower()
        if CONF_REALM in data
        else data[CONF_AUTH_PROVIDERS].lower()
    )
    data[CONF_USERNAME] = f"{username}@{realm}"
    return data
