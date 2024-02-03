"""MotionBlinds BLE integration."""
from __future__ import annotations

import logging

from motionblindsble.crypt import MotionCrypt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MAC_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.COVER,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.BUTTON,
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up MotionBlinds BLE integration."""

    _LOGGER.info("Setting up MotionBlinds BLE integration")

    # The correct time is needed for encryption
    _LOGGER.info("Setting timezone for encryption: %s", hass.config.time_zone)
    MotionCrypt.set_timezone(hass.config.time_zone)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MotionBlinds BLE device from a config entry."""

    _LOGGER.info("(%s) Setting up device", entry.data[CONF_MAC_CODE])

    hass.data.setdefault(DOMAIN, {})

    # First setup cover since sensor, select and button entities require the cover
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.COVER])
    await hass.config_entries.async_forward_entry_setups(
        entry,
        [Platform.SENSOR, Platform.SELECT, Platform.BUTTON],
    )

    _LOGGER.info("(%s) Finished setting up device", entry.data[CONF_MAC_CODE])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload MotionBlinds BLE device from a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
