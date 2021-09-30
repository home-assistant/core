"""The vizio component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyvizio.const import APPS
from pyvizio.util import gen_apps_list_from_url
import voluptuous as vol

from homeassistant.components.media_player import DEVICE_CLASS_TV
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_APPS, CONF_DEVICE_CLASS, DOMAIN, VIZIO_SCHEMA

_LOGGER = logging.getLogger(__name__)


def validate_apps(config: ConfigType) -> ConfigType:
    """Validate CONF_APPS is only used when CONF_DEVICE_CLASS == DEVICE_CLASS_TV."""
    if (
        config.get(CONF_APPS) is not None
        and config[CONF_DEVICE_CLASS] != DEVICE_CLASS_TV
    ):
        raise vol.Invalid(
            f"'{CONF_APPS}' can only be used if {CONF_DEVICE_CLASS}' is '{DEVICE_CLASS_TV}'"
        )

    return config


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [vol.All(VIZIO_SCHEMA, validate_apps)])},
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["media_player"]


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
        and entry.data[CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
    ):
        coordinator = VizioAppsDataUpdateCoordinator(hass)
        await coordinator.async_refresh()
        hass.data[DOMAIN][CONF_APPS] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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
        and entry.data[CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
        for entry in hass.config_entries.async_entries(DOMAIN)
    ):
        hass.data[DOMAIN].pop(CONF_APPS, None)

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return unload_ok


class VizioAppsDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Vizio app config data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(days=1),
            update_method=self._async_update_data,
        )
        self.data = APPS
        self.fail_count = 0
        self.fail_threshold = 10

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update data via library."""
        data = await gen_apps_list_from_url(session=async_get_clientsession(self.hass))
        if not data:
            # For every failure, increase the fail count until we reach the threshold.
            # We then log a warning, increase the threshold, and reset the fail count.
            # This is here to prevent silent failures but to reduce repeat logs.
            if self.fail_count == self.fail_threshold:
                _LOGGER.warning(
                    (
                        "Unable to retrieve the apps list from the external server "
                        "for the last %s days"
                    ),
                    self.fail_threshold,
                )
                self.fail_count = 0
                self.fail_threshold += 10
            else:
                self.fail_count += 1
            return self.data
        # Reset the fail count and threshold when the data is successfully retrieved
        self.fail_count = 0
        self.fail_threshold = 10
        return sorted(data, key=lambda app: app["name"])
