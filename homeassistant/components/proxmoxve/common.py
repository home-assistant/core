"""Common methods for Proxmox VE integration."""

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_AUTH_PROVIDERS, CONF_PASSWORD, CONF_USERNAME

from .const import AUTH_OTHER, CONF_REALM, CONF_TOKEN_SECRET


def sanitize_config_entry(
    input_data: Mapping[str, Any], strip_credentials: bool = False
) -> dict[str, Any]:
    """Sanitize the user ID and realm in config_entry data."""
    data = dict(input_data)
    username = data[CONF_USERNAME].split("@")[0]
    provider = data[CONF_AUTH_PROVIDERS]

    realm = provider.lower()
    if provider == AUTH_OTHER:
        realm = data[CONF_REALM].lower()

    data[CONF_REALM] = realm
    data[CONF_USERNAME] = f"{username}@{realm}"

    if not strip_credentials:
        return data

    # Strip credentials for reauth/reconfigure
    if data.get(CONF_TOKEN_SECRET):
        data[CONF_TOKEN_SECRET] = None
    if data.get(CONF_PASSWORD):
        data[CONF_PASSWORD] = None

    return data
