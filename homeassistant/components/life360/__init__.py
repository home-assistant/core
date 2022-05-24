"""Life360 integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_AUTHORIZATION,
    CONF_CIRCLES,
    CONF_DRIVING_SPEED,
    CONF_ERROR_THRESHOLD,
    CONF_MAX_GPS_ACCURACY,
    CONF_MAX_UPDATE_WAIT,
    CONF_MEMBERS,
    CONF_PREFIX,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_AS_STATE,
    CONF_WARNING_THRESHOLD,
    DEFAULT_SCAN_INTERVAL_SEC,
    DEFAULT_SCAN_INTERVAL_TD,
    DOMAIN,
    LOGGER,
    OPTIONS,
    SHOW_DRIVING,
    SHOW_MOVING,
)
from .helpers import AccountData, get_life360_api, get_life360_data, init_integ_data

PLATFORMS = [Platform.DEVICE_TRACKER]
DEFAULT_PREFIX = DOMAIN

SHOW_AS_STATE_OPTS = [SHOW_DRIVING, SHOW_MOVING]

_UNUSED_CONF = (
    CONF_CIRCLES,
    CONF_ERROR_THRESHOLD,
    CONF_MAX_UPDATE_WAIT,
    CONF_MEMBERS,
    CONF_WARNING_THRESHOLD,
)


def _prefix(value: None | str) -> None | str:
    if value == "":
        return None
    return value


LIFE360_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DRIVING_SPEED): vol.Coerce(float),
        vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
        vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): vol.All(
            vol.Any(None, cv.string), _prefix
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_SEC): vol.Coerce(
            float
        ),
        vol.Optional(CONF_SHOW_AS_STATE, default=[]): vol.All(
            cv.ensure_list, [vol.In(SHOW_AS_STATE_OPTS)]
        ),
    },
    extra=vol.ALLOW_EXTRA,
)
CONFIG_SCHEMA = vol.Schema({DOMAIN: LIFE360_SCHEMA}, extra=vol.ALLOW_EXTRA)


def _update_interval(entry: ConfigEntry) -> timedelta:
    try:
        return timedelta(seconds=entry.options[CONF_SCAN_INTERVAL])
    except KeyError:
        return DEFAULT_SCAN_INTERVAL_TD


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration."""
    cfg_options = {}
    if conf := config.get(DOMAIN):
        if any(
            entry.version == 1 for entry in hass.config_entries.async_entries(DOMAIN)
        ):
            # Need config options, if any, for migration.
            if unused_conf := [k for k in conf if k in _UNUSED_CONF]:
                LOGGER.warning(
                    "The following options are no longer supported: %s",
                    ", ".join(unused_conf),
                )
            cfg_options = {k: conf[k] for k in OPTIONS if conf.get(k) is not None}
            if show_as_state := conf.get(CONF_SHOW_AS_STATE):
                if SHOW_DRIVING in show_as_state:
                    cfg_options[SHOW_DRIVING] = True
                if SHOW_MOVING in show_as_state:
                    LOGGER.warning(
                        "%s is no longer supported as an option for %s",
                        SHOW_MOVING,
                        CONF_SHOW_AS_STATE,
                    )
        else:
            LOGGER.warning("Setup via configuration no longer supported")

    init_integ_data(hass, cfg_options)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry."""
    LOGGER.debug("Migrating config entry from version %s", entry.version)

    if entry.version == 1:
        entry.version = 2
        entry.source = SOURCE_USER
        unique_id = entry.data[CONF_USERNAME].lower()
        hass.config_entries.async_update_entry(
            entry,
            unique_id=unique_id,
            title=unique_id,
            options=hass.data[DOMAIN]["cfg_options"],
        )

    LOGGER.info("Config entry migration to version %s successful", entry.version)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    account = hass.data[DOMAIN]["accounts"].setdefault(
        cast(str, entry.unique_id), AccountData()
    )

    if not (api := account.get("api")):
        api = get_life360_api(authorization=entry.data[CONF_AUTHORIZATION])
        account["api"] = api

    async def async_update_data() -> dict[str, dict[str, Any]]:
        """Update Life360 data."""
        return await get_life360_data(hass, api)

    if not (coordinator := account.get("coordinator")):
        coordinator = account["coordinator"] = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{DOMAIN} ({entry.unique_id})",
            update_interval=_update_interval(entry),
            update_method=async_update_data,
        )

    await coordinator.async_config_entry_first_refresh()

    # Set up components for our platforms.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # Add event listener for option flow changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    # Unload components for our platforms.
    # But first stop checking for new members on update.
    if unsub := hass.data[DOMAIN]["accounts"][entry.unique_id].pop("unsub", None):
        unsub()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove config entry."""
    try:
        del hass.data[DOMAIN]["accounts"][entry.unique_id]
    except KeyError:
        pass


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    account = hass.data[DOMAIN]["accounts"][entry.unique_id]
    account["coordinator"].update_interval = _update_interval(entry)

    # Some option changes (e.g., prefix, aka entity_namespace) require entities to be
    # recreated.
    if account.pop("re_add_entry", False):
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.config_entries.async_add(entry)
