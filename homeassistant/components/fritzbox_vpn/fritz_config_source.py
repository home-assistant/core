"""Config source from existing FritzBox/AVM integrations for config flow. Repeaters excluded."""

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    FRITZ_INTEGRATION_DOMAINS,
    REPEATER_INDICATORS,
    password_from_sources,
)

_LOGGER = logging.getLogger(__name__)


def _entry_has_credentials(entry: config_entries.ConfigEntry) -> bool:
    """True if entry has username or password in data or options."""
    data = entry.data or {}
    options = entry.options or {}
    if data.get(CONF_USERNAME) or data.get("username") or data.get("user"):
        return True
    if options.get(CONF_USERNAME) or options.get("username") or options.get("user"):
        return True
    return bool(password_from_sources(data, options))


def _host_username_password_from_entry(entry: config_entries.ConfigEntry) -> dict[str, Any] | None:
    """Host, username, password from entry; None if no host."""
    config_data = entry.data or {}
    options_data = entry.options or {}
    host = (
        config_data.get(CONF_HOST)
        or config_data.get("host")
        or (config_data.get("hosts", [None])[0] if isinstance(config_data.get("hosts"), list) and config_data.get("hosts") else None)
        or config_data.get("hostname")
        or config_data.get("ip_address")
        or options_data.get(CONF_HOST)
        or options_data.get("host")
    )
    username = (
        config_data.get(CONF_USERNAME)
        or config_data.get("username")
        or config_data.get("user")
        or options_data.get(CONF_USERNAME)
        or options_data.get("username")
        or options_data.get("user")
    )
    password = password_from_sources(config_data, options_data)
    if not host and isinstance(config_data.get("data"), dict):
        nested = config_data["data"]
        host = host or nested.get("host") or nested.get(CONF_HOST)
        username = username or nested.get("username") or nested.get(CONF_USERNAME)
        password = password or password_from_sources(nested)
    if not host:
        return None
    return {CONF_HOST: host, CONF_USERNAME: username or "", CONF_PASSWORD: password or ""}


async def get_existing_fritz_config(hass: HomeAssistant) -> dict[str, Any] | None:
    """Config from existing Fritz/FritzBox Tools integration if available. Repeaters excluded."""
    excluded_states = (
        config_entries.ConfigEntryState.FAILED_UNLOAD,
        config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    )

    for domain in FRITZ_INTEGRATION_DOMAINS:
        try:
            all_entries = list(hass.config_entries.async_entries(domain))
        except KeyError:
            continue
        entries = [e for e in all_entries if e.state not in excluded_states]
        if not entries:
            continue

        router_entries = [
            e for e in entries
            if not any(ind in (e.title or "").lower() for ind in REPEATER_INDICATORS)
        ]
        if not router_entries:
            continue

        try:
            entries_with_creds = [e for e in router_entries if _entry_has_credentials(e)]
            entry = entries_with_creds[0] if entries_with_creds else router_entries[0]
            result = _host_username_password_from_entry(entry)
            if result:
                return result
            _LOGGER.warning(
                "FritzBox integration '%s' found but could not extract host (entry_id: %s)",
                domain,
                entry.entry_id,
            )
        except Exception as err:
            _LOGGER.warning("Error reading config from domain '%s': %s", domain, err)
    return None
