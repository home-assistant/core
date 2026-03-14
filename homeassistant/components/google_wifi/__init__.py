"""The google_wifi component."""

import logging
import requests
from datetime import timedelta
from homeassistant.util import Throttle
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (DOMAIN, ENDPOINT, MIN_TIME_BETWEEN_UPDATES, ATTR_CURRENT_VERSION, ATTR_NEW_VERSION, ATTR_UPTIME,
    ATTR_LAST_RESTART, ATTR_LOCAL_IP, ATTR_STATUS)

_LOGGER = logging.getLogger(__name__)

# Load the sensor.py file
PLATFORMS = [Platform.SENSOR]

# Define the type for entry.runtime_data
type GoogleWifiConfigEntry = ConfigEntry[GoogleWifiData]

@dataclass
class GoogleWifiData:
    """Runtime data for Google Wifi."""
    api: GoogleWifiAPI

class GoogleWifiAPI:
    """Get the latest data and update the states."""

    def __init__(self, host, conditions):
        """Initialize the data object."""
        uri = "http://"
        resource = f"{uri}{host}{ENDPOINT}"
        self._request = requests.Request("GET", resource).prepare()
        self.raw_data = None
        self.conditions = conditions
        self.data = {
            ATTR_CURRENT_VERSION: None,
            ATTR_NEW_VERSION: None,
            ATTR_UPTIME: None,
            ATTR_LAST_RESTART: None,
            ATTR_LOCAL_IP: None,
            ATTR_STATUS: None,
        }
        self.available = True
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the router."""
        try:
            with requests.Session() as sess:
                response = sess.send(self._request, timeout=10)
            self.raw_data = response.json()
            self.data_format()
            self.available = True
        except ValueError, requests.exceptions.ConnectionError:
            _LOGGER.warning("Unable to fetch data from Google Wifi")
            self.available = False
            self.raw_data = None

    def data_format(self):
        """Format raw data into easily accessible dict."""
        for description in SENSOR_TYPES:
            if description.key not in self.conditions:
                continue
            attr_key = description.key
            try:
                if description.primary_key in self.raw_data:
                    sensor_value = self.raw_data[description.primary_key][
                        description.sensor_key
                    ]
                    # Format sensor for better readability
                    if attr_key == ATTR_NEW_VERSION and sensor_value == "0.0.0.0":
                        sensor_value = "Latest"
                    elif attr_key == ATTR_UPTIME:
                        sensor_value = round(sensor_value / (3600 * 24), 2)
                    elif attr_key == ATTR_LAST_RESTART:
                        last_restart = dt_util.now() - timedelta(seconds=sensor_value)
                        sensor_value = last_restart.strftime("%Y-%m-%d %H:%M:%S")
                    elif attr_key == ATTR_STATUS:
                        if sensor_value:
                            sensor_value = "Online"
                        else:
                            sensor_value = "Offline"
                    elif (
                        attr_key == ATTR_LOCAL_IP and not self.raw_data["wan"]["online"]
                    ):
                        sensor_value = None

                    self.data[attr_key] = sensor_value
            except KeyError:
                _LOGGER.error(
                    (
                        "Router does not support %s field. "
                        "Please remove %s from monitored_conditions"
                    ),
                    description.sensor_key,
                    attr_key,
                )
                self.data[attr_key] = None


# Pull in the config flow - entry: ConfigEntry comes from the config flow.
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Wifi from a config entry."""
    host = entry.data[CONF_IP_ADDRESS]

    conditions = [
        ATTR_CURRENT_VERSION,
        ATTR_NEW_VERSION,
        ATTR_UPTIME,
        ATTR_LAST_RESTART,
        ATTR_LOCAL_IP,
        ATTR_STATUS
    ]

    # Initialize the API in the executor because its __init__ calls self.update()
    api = await hass.async_add_executor_job(GoogleWifiAPI, host, conditions)

    # Store the API instance in runtime_data
    entry.runtime_data = GoogleWifiData(api=api)

    # Setup the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register listener for updates
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    # Tell Home Assistant to unload the platforms we set up earlier
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # If successful, remove the stored data from memory
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

