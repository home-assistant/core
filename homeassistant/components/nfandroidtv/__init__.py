"""The NFAndroidTV integration."""

import logging

from notifications_android_tv.notifications import ConnectError, Notifications

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import DATA_HASS_CONFIG, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
type NFAndroidTVConfigEntry = ConfigEntry[Notifications]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NFAndroidTV component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NFAndroidTV from a config entry."""

    try:
        entry.runtime_data = await hass.async_add_executor_job(
            Notifications, entry.data[CONF_HOST]
        )
    except ConnectError as e:
        _LOGGER.debug("Error", exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
        ) from e

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_NAME: entry.title, **entry.data},
            hass.data[DATA_HASS_CONFIG],
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
