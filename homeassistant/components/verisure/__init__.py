"""Support for Verisure devices."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import os
from typing import Any

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_CODE_DIGITS,
    CONF_DEFAULT_LOCK_CODE,
    CONF_GIID,
    CONF_LOCK_CODE_DIGITS,
    CONF_LOCK_DEFAULT_CODE,
    DEFAULT_LOCK_CODE_DIGITS,
    DOMAIN,
)
from .coordinator import VerisureDataUpdateCoordinator

PLATFORMS = [
    ALARM_CONTROL_PANEL_DOMAIN,
    BINARY_SENSOR_DOMAIN,
    CAMERA_DOMAIN,
    LOCK_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
]

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Optional(CONF_CODE_DIGITS): cv.positive_int,
                    vol.Optional(CONF_GIID): cv.string,
                    vol.Optional(CONF_DEFAULT_LOCK_CODE): cv.string,
                },
                extra=vol.ALLOW_EXTRA,
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Verisure integration."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_EMAIL: config[DOMAIN][CONF_USERNAME],
                    CONF_PASSWORD: config[DOMAIN][CONF_PASSWORD],
                    CONF_GIID: config[DOMAIN].get(CONF_GIID),
                    CONF_LOCK_CODE_DIGITS: config[DOMAIN].get(CONF_CODE_DIGITS),
                    CONF_LOCK_DEFAULT_CODE: config[DOMAIN].get(CONF_LOCK_DEFAULT_CODE),
                },
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Verisure from a config entry."""
    # Migrate old YAML settings (hidden in the config entry),
    # to config entry options. Can be removed after YAML support is gone.
    if CONF_LOCK_CODE_DIGITS in entry.data or CONF_DEFAULT_LOCK_CODE in entry.data:
        options = entry.options.copy()

        if (
            CONF_LOCK_CODE_DIGITS in entry.data
            and CONF_LOCK_CODE_DIGITS not in entry.options
            and entry.data[CONF_LOCK_CODE_DIGITS] != DEFAULT_LOCK_CODE_DIGITS
        ):
            options.update(
                {
                    CONF_LOCK_CODE_DIGITS: entry.data[CONF_LOCK_CODE_DIGITS],
                }
            )

        if (
            CONF_DEFAULT_LOCK_CODE in entry.data
            and CONF_DEFAULT_LOCK_CODE not in entry.options
        ):
            options.update(
                {
                    CONF_DEFAULT_LOCK_CODE: entry.data[CONF_DEFAULT_LOCK_CODE],
                }
            )

        data = entry.data.copy()
        data.pop(CONF_LOCK_CODE_DIGITS, None)
        data.pop(CONF_DEFAULT_LOCK_CODE, None)
        hass.config_entries.async_update_entry(entry, data=data, options=options)

    # Continue as normal...
    coordinator = VerisureDataUpdateCoordinator(hass, entry=entry)

    if not await coordinator.async_login():
        raise ConfigEntryAuthFailed

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.async_logout)
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up all platforms for this device/entry.
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Verisure config entry."""
    unload_ok = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            )
        )
    )

    if not unload_ok:
        return False

    cookie_file = hass.config.path(STORAGE_DIR, f"verisure_{entry.entry_id}")
    with suppress(FileNotFoundError):
        await hass.async_add_executor_job(os.unlink, cookie_file)

    del hass.data[DOMAIN][entry.entry_id]

    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return True
