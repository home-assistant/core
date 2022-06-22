"""Life360 integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_AUTHORIZATION,
    CONF_DRIVING_SPEED,
    CONF_MAX_GPS_ACCURACY,
    CONF_SHOW_AS_STATE,
    DEFAULT_OPTIONS,
    DEFAULT_SCAN_INTERVAL_TD,
    DOMAIN,
    LOGGER,
    OPTIONS,
    SHOW_DRIVING,
    SHOW_MOVING,
    UNUSED_CONF,
)
from .helpers import Life360Data, get_life360_api, get_life360_data, init_integ_data

PLATFORMS = [Platform.DEVICE_TRACKER]

SHOW_AS_STATE_OPTS = [SHOW_DRIVING, SHOW_MOVING]

LIFE360_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DRIVING_SPEED): vol.Coerce(float),
        vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
        vol.Optional(CONF_SHOW_AS_STATE, default=[]): vol.All(
            cv.ensure_list, [vol.In(SHOW_AS_STATE_OPTS)]
        ),
    },
    extra=vol.ALLOW_EXTRA,
)
CONFIG_SCHEMA = vol.Schema({DOMAIN: LIFE360_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration."""
    cfg_options = {}
    if conf := config.get(DOMAIN):
        LOGGER.warning("Setup via configuration no longer supported")
        # Need config options, if any, for migration.
        if unused_conf := [k for k in conf if k in UNUSED_CONF]:
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

    init_integ_data(hass, cfg_options)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    init_integ_data(hass)

    # Check if this entry was created when this was a "legacy" tracker. If it was,
    # update with missing data.
    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=entry.data[CONF_USERNAME].lower(),
            options=DEFAULT_OPTIONS | hass.data[DOMAIN].cfg_options,
        )

    api = get_life360_api(authorization=entry.data[CONF_AUTHORIZATION])

    async def async_update_data() -> Life360Data:
        """Update Life360 data."""
        return await get_life360_data(hass, api)

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN} ({entry.unique_id})",
        update_interval=DEFAULT_SCAN_INTERVAL_TD,
        update_method=async_update_data,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN].coordinators[entry.entry_id] = coordinator

    # Set up components for our platforms.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    del hass.data[DOMAIN].coordinators[entry.entry_id]

    # Unload components for our platforms.
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
