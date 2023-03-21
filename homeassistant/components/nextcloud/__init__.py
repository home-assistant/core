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
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nextcloud integration."""
    # Fetch Nextcloud Monitor api data
    conf = config[DOMAIN]

    try:
        ncm = NextcloudMonitor(conf[CONF_URL], conf[CONF_USERNAME], conf[CONF_PASSWORD])
    except NextcloudMonitorError:
        _LOGGER.error("Nextcloud setup failed - Check configuration")
        return False

    hass.data[DOMAIN] = get_data_points(ncm.data)
    hass.data[DOMAIN]["instance"] = conf[CONF_URL]

    def nextcloud_update(event_time):
        """Update data from nextcloud api."""
        try:
            ncm.update()
        except NextcloudMonitorError:
            _LOGGER.error("Nextcloud update failed")
            return False

        hass.data[DOMAIN] = get_data_points(ncm.data)
        hass.data[DOMAIN]["instance"] = conf[CONF_URL]

    # Update sensors on time interval
    track_time_interval(hass, nextcloud_update, conf[CONF_SCAN_INTERVAL])

    for platform in PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True


# Use recursion to create list of sensors & values based on nextcloud api data
def get_data_points(api_data, key_path="", leaf=False):
    """Use Recursion to discover data-points and values.

    Get dictionary of data-points by recursing through dict returned by api until
    the dictionary value does not contain another dictionary and use the
    resulting path of dictionary keys and resulting value as the name/value
    for the data-point.

    returns: dictionary of data-point/values
    """
    result = {}
    for key, value in api_data.items():
        if isinstance(value, dict):
            if leaf:
                key_path = f"{key}_"
            if not leaf:
                key_path += f"{key}_"
            leaf = True
            result.update(get_data_points(value, key_path, leaf))
        else:
            result[f"{DOMAIN}_{key_path}{key}"] = value
            leaf = False
    return result
