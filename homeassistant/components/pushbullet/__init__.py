"""The pushbullet component."""
from __future__ import annotations

import logging

from pushbullet import InvalidKeyError, PushBullet, PushbulletError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .api import PushBulletNotificationProvider
from .const import DATA_HASS_CONFIG, DOMAIN

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the pushbullet component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up pushbullet from a config entry."""

    try:
        pushbullet = await hass.async_add_executor_job(
            PushBullet, entry.data[CONF_API_KEY]
        )
    except InvalidKeyError:
        _LOGGER.error("Invalid API key for Pushbullet")
        return False
    except PushbulletError as err:
        raise ConfigEntryNotReady from err

    pb_provider = PushBulletNotificationProvider(hass, pushbullet)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = pb_provider

    def start_listener(event: Event) -> None:
        """Start the listener thread."""
        _LOGGER.debug("Starting listener for pushbullet")
        pb_provider.start()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_listener)

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_NAME: entry.data[CONF_NAME], "entry_id": entry.entry_id},
            hass.data[DATA_HASS_CONFIG],
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        pb_provider: PushBulletNotificationProvider = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        await hass.async_add_executor_job(pb_provider.close)
    return unload_ok
