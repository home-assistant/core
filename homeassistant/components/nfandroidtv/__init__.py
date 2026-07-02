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
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
type NFAndroidTVConfigEntry = ConfigEntry[Notifications]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NFAndroidTV component."""

    hass.data[DATA_HASS_CONFIG] = config

    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NFAndroidTVConfigEntry) -> bool:
    """Set up NFAndroidTV from a config entry."""

    try:
        client = await hass.async_add_executor_job(Notifications, entry.data[CONF_HOST])
    except ConnectError as e:
        _LOGGER.debug("Full exception:", exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
            translation_placeholders={CONF_NAME: entry.title},
        ) from e

    entry.runtime_data = client

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


async def async_unload_entry(
    hass: HomeAssistant, entry: NFAndroidTVConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
