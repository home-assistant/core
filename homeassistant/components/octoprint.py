"""
Support for monitoring OctoPrint 3D printers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/octoprint/
"""
import logging

import time
import requests

from homeassistant.components import discovery
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.helpers import validate_config

DOMAIN = "octoprint"
OCTOPRINT = None

_LOGGER = logging.getLogger(__name__)

DISCOVER_SENSORS = 'octoprint.sensors'
DISCOVER_BINARY_SENSORS = 'octoprint.binary_sensor'


def setup(hass, config):
    """Set up OctoPrint API."""
    if not validate_config(config, {DOMAIN: [CONF_API_KEY],
                                    DOMAIN: [CONF_HOST]},
                           _LOGGER):
        return False

    base_url = config[DOMAIN][CONF_HOST] + "/api/"
    api_key = config[DOMAIN][CONF_API_KEY]

    global OCTOPRINT
    try:
        OCTOPRINT = OctoPrintAPI(base_url, api_key)
        OCTOPRINT.get("printer")
        OCTOPRINT.get("job")
    except requests.exceptions.RequestException as conn_err:
        _LOGGER.error("Error setting up OctoPrint API: %r", conn_err)
        return False

    for component, discovery_service in (
            ('sensor', DISCOVER_SENSORS),
            ('binary_sensor', DISCOVER_BINARY_SENSORS)):
        discovery.discover(hass, discovery_service, component=component,
                           hass_config=config)

    return True


class OctoPrintAPI(object):
    """Simple JSON wrapper for OctoPrint's API."""

    def __init__(self, api_url, key):
        """Initialize OctoPrint API and set headers needed later."""
        self.api_url = api_url
        self.headers = {'content-type': 'application/json',
                        'X-Api-Key': key}
        self.printer_last_reading = [{}, None]
        self.job_last_reading = [{}, None]

    def get_tools(self):
        """Get the dynamic list of tools that temperature is monitored on."""
        tools = self.printer_last_reading[0]['temperature']
        return tools.keys()

    def get(self, endpoint):
        """Send a get request, and return the response as a dict."""
        now = time.time()
        if endpoint == "job":
            last_time = self.job_last_reading[1]
            if last_time is not None:
                if now - last_time < 30.0:
                    return self.job_last_reading[0]
        elif endpoint == "printer":
            last_time = self.printer_last_reading[1]
            if last_time is not None:
                if now - last_time < 30.0:
                    return self.printer_last_reading[0]
        url = self.api_url + endpoint
        try:
            response = requests.get(url,
                                    headers=self.headers,
                                    timeout=30)
            response.raise_for_status()
            if endpoint == "job":
                self.job_last_reading[0] = response.json()
                self.job_last_reading[1] = time.time()
            elif endpoint == "printer":
                self.printer_last_reading[0] = response.json()
                self.printer_last_reading[1] = time.time()
            return response.json()
        except requests.exceptions.ConnectionError as conn_exc:
            _LOGGER.error("Failed to update OctoPrint status.  Error: %s",
                          conn_exc)
            raise

    def update(self, sensor_type, end_point, group, tool=None):
        """Return the value for sensor_type from the provided endpoint."""
        try:
            return get_value_from_json(self.get(end_point), sensor_type,
                                       group, tool)
        except requests.exceptions.ConnectionError:
            raise


# pylint: disable=unused-variable
def get_value_from_json(json_dict, sensor_type, group, tool):
    """Return the value for sensor_type from the JSON."""
    if group in json_dict:
        if sensor_type in json_dict[group]:
            if sensor_type == "target" and json_dict[sensor_type] is None:
                return 0
            else:
                return json_dict[group][sensor_type]
        elif tool is not None:
            if sensor_type in json_dict[group][tool]:
                return json_dict[group][tool][sensor_type]
