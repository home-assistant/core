"""The vizio component."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import CONF_APPS, CONF_DEVICE_CLASS, DOMAIN, VIZIO_SCHEMA
from .coordinator import VizioAppsDataUpdateCoordinator


def validate_apps(config: ConfigType) -> ConfigType:
    """Validate CONF_APPS is only used when CONF_DEVICE_CLASS is MediaPlayerDeviceClass.TV."""
    if (
        config.get(CONF_APPS) is not None
        and config[CONF_DEVICE_CLASS] != MediaPlayerDeviceClass.TV
    ):
        raise vol.Invalid(
            f"'{CONF_APPS}' can only be used if {CONF_DEVICE_CLASS}' is"
            f" '{MediaPlayerDeviceClass.TV}'"
        )

    return config


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [vol.All(VIZIO_SCHEMA, validate_apps)])},
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Component setup, run import config flow for each entry in config."""
    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the saved entities."""

    hass.data.setdefault(DOMAIN, {})
    if (
        CONF_APPS not in hass.data[DOMAIN]
        and entry.data[CONF_DEVICE_CLASS] == MediaPlayerDeviceClass.TV
    ):
        store: Store[list[dict[str, Any]]] = Store(hass, 1, DOMAIN)
        coordinator = VizioAppsDataUpdateCoordinator(hass, store)
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][CONF_APPS] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    # Exclude this config entry because its not unloaded yet
    if not any(
        entry.state is ConfigEntryState.LOADED
        and entry.entry_id != config_entry.entry_id
        and entry.data[CONF_DEVICE_CLASS] == MediaPlayerDeviceClass.TV
        for entry in hass.config_entries.async_entries(DOMAIN)
    ):
        hass.data[DOMAIN].pop(CONF_APPS, None)

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return unload_ok
