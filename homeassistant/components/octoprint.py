"""
Support for monitoring OctoPrint 3D printers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/octoprint/
"""
import logging
import time

import requests
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONTENT_TYPE_JSON
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'octoprint'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_HOST): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the OctoPrint component."""
    base_url = 'http://{}/api/'.format(config[DOMAIN][CONF_HOST])
    api_key = config[DOMAIN][CONF_API_KEY]

    hass.data[DOMAIN] = {"api": None}

    try:
        octoprint_api = OctoPrintAPI(base_url, api_key)
        hass.data[DOMAIN]["api"] = octoprint_api
        octoprint_api.get('printer')
        octoprint_api.get('job')
    except requests.exceptions.RequestException as conn_err:
        _LOGGER.error("Error setting up OctoPrint API: %r", conn_err)

    return True


class OctoPrintAPI(object):
    """Simple JSON wrapper for OctoPrint's API."""

    def __init__(self, api_url, key):
        """Initialize OctoPrint API and set headers needed later."""
        self.api_url = api_url
        self.headers = {'content-type': CONTENT_TYPE_JSON,
                        'X-Api-Key': key}
        self.printer_last_reading = [{}, None]
        self.job_last_reading = [{}, None]
        self.job_available = False
        self.printer_available = False
        self.available = False
        self.printer_error_logged = False
        self.job_error_logged = False

    def get_tools(self):
        """Get the dynamic list of tools that temperature is monitored on."""
        tools = self.printer_last_reading[0]['temperature']
        return tools.keys()

    def get(self, endpoint):
        """Send a get request, and return the response as a dict."""
        # Only query the API at most every 30 seconds
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
            response = requests.get(
                url, headers=self.headers, timeout=9)
            response.raise_for_status()
            if endpoint == "job":
                self.job_last_reading[0] = response.json()
                self.job_last_reading[1] = time.time()
                self.job_available = True
            elif endpoint == "printer":
                self.printer_last_reading[0] = response.json()
                self.printer_last_reading[1] = time.time()
                self.printer_available = True
            self.available = self.printer_available and self.job_available
            if self.available:
                self.job_error_logged = False
                self.printer_error_logged = False
            return response.json()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
                requests.exceptions.ReadTimeout) as conn_exc:
            log_string = "Failed to update OctoPrint status. " + \
                               "  Error: %s" % (conn_exc)
            # Only log the first failure
            if endpoint == "job":
                log_string = "Endpoint: job " + log_string
                if not self.job_error_logged:
                    _LOGGER.error(log_string)
                    self.job_error_logged = True
                    self.job_available = False
            elif endpoint == "printer":
                log_string = "Endpoint: printer " + log_string
                if not self.printer_error_logged:
                    _LOGGER.error(log_string)
                    self.printer_error_logged = True
                    self.printer_available = False
            self.available = False
            return None

    def update(self, sensor_type, end_point, group, tool=None):
        """Return the value for sensor_type from the provided endpoint."""
        response = self.get(end_point)
        if response is not None:
            return get_value_from_json(response, sensor_type, group, tool)
        return response


# pylint: disable=unused-variable
def get_value_from_json(json_dict, sensor_type, group, tool):
    """Return the value for sensor_type from the JSON."""
    if group not in json_dict:
        return None

    if sensor_type in json_dict[group]:
        if sensor_type == "target" and json_dict[sensor_type] is None:
            return 0
        return json_dict[group][sensor_type]

    elif tool is not None:
        if sensor_type in json_dict[group][tool]:
            return json_dict[group][tool][sensor_type]

    return None
