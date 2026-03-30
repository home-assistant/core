"""Common methods for Proxmox VE integration."""

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_USERNAME

from .const import AUTH_OTHER, CONF_AUTH_METHOD, CONF_REALM


def sanitize_config_entry(input_data: Mapping[str, Any]) -> dict[str, Any]:
    """Sanitize the user ID and realm in config_entry data."""
    data = dict(input_data)
    username = data[CONF_USERNAME].split("@")[0]
    provider = data[CONF_AUTH_METHOD]

    realm = provider.lower()
    if provider == AUTH_OTHER:
        realm = data[CONF_REALM].lower()

    data[CONF_REALM] = realm
    data[CONF_USERNAME] = f"{username}@{realm}"

    return data
