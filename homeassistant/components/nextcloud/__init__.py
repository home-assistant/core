"""The Nextcloud integration."""
import logging

from nextcloudmonitor import NextcloudMonitor, NextcloudMonitorError
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = (Platform.SENSOR, Platform.BINARY_SENSOR)

# Validate user configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nextcloud integration."""
    conf = config[DOMAIN]

    try:
        ncm = await hass.async_add_executor_job(
            NextcloudMonitor, conf[CONF_URL], conf[CONF_USERNAME], conf[CONF_PASSWORD]
        )
    except NextcloudMonitorError:
        _LOGGER.error("Nextcloud setup failed - Check configuration")
        return False

    coordinator = NextcloudDataUpdateCoordinator(
        hass,
        ncm,
        conf,
    )
    hass.data[DOMAIN] = coordinator

    await coordinator.async_config_entry_first_refresh()

    for platform in PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True
