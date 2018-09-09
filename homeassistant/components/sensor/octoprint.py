"""
Support for monitoring OctoPrint sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.octoprint/
"""
import logging
import time

import requests
import voluptuous as vol

from aiohttp.hdrs import CONTENT_TYPE
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (TEMP_CELSIUS, CONF_NAME, CONF_API_KEY,
                                 CONF_MONITORED_CONDITIONS, CONF_HOST,
                                 CONTENT_TYPE_JSON)

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_NUMBER_OF_TOOLS = 'number_of_tools'
CONF_BED = 'bed'
DOMAIN = "octoprint"
DEFAULT_NAME = 'OctoPrint'
NOTIFICATION_ID = 'octoprint_notification'
NOTIFICATION_TITLE = 'OctoPrint sensor setup error'

SENSOR_TYPES = {
    'Temperatures': ['printer', 'temperature', '*', TEMP_CELSIUS],
    'Current State': ['printer', 'state', 'text', None, 'mdi:printer-3d'],
    'Job Percentage': ['job', 'progress', 'completion', '%',
                       'mdi:file-percent'],
    'Time Remaining': ['job', 'progress', 'printTimeLeft', 'seconds',
                       'mdi:clock-end'],
    'Time Elapsed': ['job', 'progress', 'printTime', 'seconds',
                     'mdi:clock-start'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NUMBER_OF_TOOLS, default=0): cv.positive_int,
    vol.Optional(CONF_BED, default=False): cv.boolean,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available OctoPrint sensors."""
    host = config.get(CONF_HOST)
    octoprint_api = OctoPrintAPI('http://{}/api/'.format(host),
                                 config.get(CONF_API_KEY),
                                 config.get(CONF_BED),
                                 config.get(CONF_NUMBER_OF_TOOLS))
    name = config.get(CONF_NAME)
    monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)
    tools = octoprint_api.get_tools()

    if "Temperatures" in monitored_conditions:
        if not tools:
            hass.components.persistent_notification.create(
                'Your {} printer appears to be offline.<br />'
                'If you do not want to have your printer on <br />'
                ' at all times, and you would like to monitor <br /> '
                'temperatures, please add <br />'
                'bed and/or number&#95of&#95tools to your config <br />'
                'and restart.'.format(name),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)

    devices = []
    types = ["actual", "target"]
    for octo_type in monitored_conditions:
        if octo_type == "Temperatures":
            for tool in tools:
                for temp_type in types:
                    new_sensor = OctoPrintSensor(
                        octoprint_api, temp_type, temp_type, name,
                        SENSOR_TYPES[octo_type][3], SENSOR_TYPES[octo_type][0],
                        SENSOR_TYPES[octo_type][1], tool)
                    devices.append(new_sensor)
        else:
            new_sensor = OctoPrintSensor(
                octoprint_api, octo_type, SENSOR_TYPES[octo_type][2],
                name, SENSOR_TYPES[octo_type][3], SENSOR_TYPES[octo_type][0],
                SENSOR_TYPES[octo_type][1], None, SENSOR_TYPES[octo_type][4])
            devices.append(new_sensor)
    add_entities(devices, True)


class OctoPrintSensor(Entity):
    """Representation of an OctoPrint sensor."""

    def __init__(self, api, condition, sensor_type, sensor_name, unit,
                 endpoint, group, tool=None, icon=None):
        """Initialize a new OctoPrint sensor."""
        self.sensor_name = sensor_name
        if tool is None:
            self._name = '{} {}'.format(sensor_name, condition)
        else:
            self._name = '{} {} {} {}'.format(
                sensor_name, condition, tool, 'temp')
        self.sensor_type = sensor_type
        self.api = api
        self._state = None
        self._unit_of_measurement = unit
        self._icon = icon
        self.api_endpoint = endpoint
        self.api_group = group
        self.api_tool = tool
        _LOGGER.debug("Created OctoPrint sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        sensor_unit = self.unit_of_measurement
        if sensor_unit in (TEMP_CELSIUS, "%"):
            # API sometimes returns null and not 0
            if self._state is None:
                self._state = 0
            return round(self._state, 2)
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    def update(self):
        """Update state of sensor."""
        try:
            self._state = self.api.update(
                self.sensor_type, self.api_endpoint, self.api_group,
                self.api_tool)
        except requests.exceptions.ConnectionError:
            # Error calling the api, already logged in api.update()
            return


class OctoPrintAPI:
    """Simple JSON wrapper for OctoPrint's API."""

    def __init__(self, api_url, key, bed, number_of_tools):
        """Initialize OctoPrint API and set headers needed later."""
        self.api_url = api_url
        self.headers = {
            CONTENT_TYPE: CONTENT_TYPE_JSON,
            'X-Api-Key': key,
        }
        self.printer_last_reading = [{}, None]
        self.job_last_reading = [{}, None]
        self.job_available = False
        self.printer_available = False
        self.available = False
        self.printer_error_logged = False
        self.job_error_logged = False
        self.bed = bed
        self.number_of_tools = number_of_tools

    def get_tools(self):
        """Get the list of tools that temperature is monitored on."""
        tools = []
        if self.number_of_tools > 0:
            for tool_number in range(0, self.number_of_tools):
                tools.append("tool" + str(tool_number))
        if self.bed:
            tools.append('bed')
        if not self.bed and self.number_of_tools == 0:
            temps = self.printer_last_reading[0].get('temperature')
            if temps is not None:
                tools = temps.keys()
        return tools

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
        except Exception as conn_exc:  # pylint: disable=broad-except
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


def get_value_from_json(json_dict, sensor_type, group, tool):
    """Return the value for sensor_type from the JSON."""
    if group not in json_dict:
        return None

    if sensor_type in json_dict[group]:
        if sensor_type == "target" and json_dict[sensor_type] is None:
            return 0
        return json_dict[group][sensor_type]

    if tool is not None:
        if sensor_type in json_dict[group][tool]:
            return json_dict[group][tool][sensor_type]

    return None
