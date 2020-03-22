"""The Nextcloud integration."""
from datetime import timedelta
import logging

from nextcloudmonitor import NextcloudMonitor, NextcloudMonitorError
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "nextcloud"

SCAN_INTERVAL = timedelta(seconds=60)

# Validate user configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
BINARY_SENSORS = (
    "nextcloud_system_enable_avatars",
    "nextcloud_system_enable_previews",
    "nextcloud_system_filelocking.enabled",
    "nextcloud_system_debug",
)


def setup(hass, config):
    """Set up the Nextcloud sensor platform."""
    # Fetch Nextcloud Monitor api data
    conf = config["sensor"][0]
    try:
        ncm = NextcloudMonitor(conf[CONF_URL], conf[CONF_USERNAME], conf[CONF_PASSWORD])
    except NextcloudMonitorError:
        _LOGGER.error("Nextcloud setup failed. Check configuration.")

    hass.data[DOMAIN] = get_sensors(ncm.data)

    def nextcloud_update(event_time):
        """Update data from nextcloud api."""
        try:
            ncm.update()
        except NextcloudMonitorError:
            _LOGGER.error("Nextcloud update failed.")

        hass.data[DOMAIN] = get_sensors(ncm.data)

    # Update sensors on time interval
    track_time_interval(hass, nextcloud_update, conf[CONF_SCAN_INTERVAL])

    discovery.load_platform(hass, "sensor", DOMAIN, {}, conf)
    discovery.load_platform(hass, "binary_sensor", DOMAIN, {}, conf)

    return True


# Use recursion to create list of sensors & values based on nextcloud api data
def get_sensors(api_data, key_path=""):
    """Use Recursion to discover sensors and values.

    Get dictionary of sensors by recursing through dict returned by api until
    the dictionary value does not contain another dictionary and use the
    resulting path of dictionary keys and resulting value as the name/value
    for the sensor.

    returns: dictionary of sensors/values
    """
    result = {}
    for key, value in api_data.items():
        if isinstance(value, dict):
            key_path += f"{key}_"
            result.update(get_sensors(value, key_path))
        else:
            result[f"{key_path}{key}"] = value
    return result
