"""Helpers for TP-Link Omada controller-level entities."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .config_flow import CONF_SITE
from .const import DOMAIN


def config_entry_controller_unique_id(config_entry: ConfigEntry) -> str | None:
    """Return the controller-level unique ID for a site config entry."""
    unique_id = config_entry.unique_id
    site_id = config_entry.data.get(CONF_SITE)

    if unique_id is None or not isinstance(site_id, str):
        return unique_id

    site_suffix = f"_{site_id}"
    if unique_id.endswith(site_suffix):
        return unique_id[: -len(site_suffix)]

    return unique_id


def config_entry_owns_controller_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Return if this site entry should add the controller-level entities."""
    controller_unique_id = config_entry_controller_unique_id(config_entry)
    controller_entries = [
        entry
        for entry in hass.config_entries.async_entries(
            DOMAIN, include_ignore=False, include_disabled=False
        )
        if config_entry_controller_unique_id(entry) == controller_unique_id
    ]

    return (
        config_entry.entry_id
        == min(
            controller_entries, key=lambda entry: (entry.created_at, entry.entry_id)
        ).entry_id
    )
