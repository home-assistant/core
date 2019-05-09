"""Support for monitoring OctoPrint 3D printers."""
import logging
import time

import requests
import voluptuous as vol
from aiohttp.hdrs import CONTENT_TYPE

from homeassistant.components.discovery import SERVICE_OCTOPRINT
from homeassistant.const import (
    CONF_API_KEY, CONF_HOST, CONTENT_TYPE_JSON, CONF_NAME, CONF_PATH,
    CONF_PORT, CONF_SSL, TEMP_CELSIUS, CONF_MONITORED_CONDITIONS, CONF_SENSORS,
    CONF_BINARY_SENSORS, ATTR_COMMAND, ATTR_NAME, ATTR_TEMPERATURE)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import slugify as util_slugify

_LOGGER = logging.getLogger(__name__)

CONF_BED = 'bed'
CONF_NUMBER_OF_TOOLS = 'number_of_tools'

DEFAULT_NAME = 'OctoPrint'
DOMAIN = 'octoprint'

ATTR_PORT = 'port'
ATTR_BAUDRATE = 'baudrate'
ATTR_PRINTER_PROFILE = 'printer_profile'

SERVICE_CANCEL_JOB = 'cancel_job'
SERVICE_COMMAND = 'command'
SERVICE_CONNECT = 'connect'
SERVICE_DISCONNECT = 'disconnect'
SERVICE_PAUSE_JOB = 'pause_job'
SERVICE_RESUME_JOB = 'resume_job'
SERVICE_TARGET_TEMPERATURE = 'target_temperature'


def has_all_unique_names(value):
    """Validate that printers have an unique name."""
    names = [util_slugify(printer['name']) for printer in value]
    vol.Schema(vol.Unique())(names)
    return value


def ensure_valid_path(value):
    """Validate the path, ensuring it starts and ends with a /."""
    vol.Schema(cv.string)(value)
    if value[0] != '/':
        value = '/' + value
    if value[-1] != '/':
        value += '/'
    return value


BINARY_SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit
    'Printing': ['printer', ['state', 'flags', 'printing'], 'moving'],
    "Printing Error": ['printer', ['state', 'flags', 'error'], 'problem']
}

BINARY_SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit, icon
    'Temperatures': ['printer', ['temperature'],
                     TEMP_CELSIUS, 'mdi:thermometer'],
    "Current State": ['printer', ['state', 'text'],
                      None, 'mdi:printer-3d'],
    "Job Percentage": ['job', ['progress', 'completion'],
                       '%', 'mdi:file-percent'],
    "Time Remaining": ['job', ['progress', 'printTimeLeft'],
                       'seconds', 'mdi:clock-end'],
    "Time Elapsed": ['job', ['progress', 'printTime'],
                     'seconds', 'mdi:clock-start'],
    "Job File": ['job', ['job', 'file', 'display'],
                 None, 'mdi:file'],
    "Printers Avaliable": ['connection', ['options', 'ports'],
                           None, 'mdi:printer-3d'],
}

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_PATH, default='/'): ensure_valid_path,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_NUMBER_OF_TOOLS, default=0): cv.positive_int,
        vol.Optional(CONF_BED, default=False): cv.boolean,
        vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
        vol.Optional(CONF_BINARY_SENSORS, default={}): BINARY_SENSOR_SCHEMA
    })], has_all_unique_names),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the OctoPrint component."""
    printers = hass.data[DOMAIN] = {}
    success = False

    def device_discovered(service, info):
        """Get called when an Octoprint server has been discovered."""
        _LOGGER.debug("Found an Octoprint server: %s", info)

    discovery.listen(hass, SERVICE_OCTOPRINT, device_discovered)

    if DOMAIN not in config:
        # Skip the setup if there is no configuration present
        return True

    for printer in config[DOMAIN]:
        name = printer[CONF_NAME]
        ssl = 's' if printer[CONF_SSL] else ''
        base_url = 'http{}://{}:{}{}api/'.format(ssl,
                                                 printer[CONF_HOST],
                                                 printer[CONF_PORT],
                                                 printer[CONF_PATH])
        api_key = printer[CONF_API_KEY]
        number_of_tools = printer[CONF_NUMBER_OF_TOOLS]
        bed = printer[CONF_BED]
        try:
            octoprint_api = OctoPrintAPI(base_url, api_key, bed,
                                         number_of_tools)
            printers[base_url] = octoprint_api
            octoprint_api.get('printer')
            octoprint_api.get('job')
        except requests.exceptions.RequestException as conn_err:
            _LOGGER.error("Error setting up OctoPrint API: %r", conn_err)
            continue

        sensors = printer[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
        load_platform(hass, 'sensor', DOMAIN, {'name': name,
                                               'base_url': base_url,
                                               'sensors': sensors}, config)
        b_sensors = printer[CONF_BINARY_SENSORS][CONF_MONITORED_CONDITIONS]
        load_platform(hass, 'binary_sensor', DOMAIN, {'name': name,
                                                      'base_url': base_url,
                                                      'sensors': b_sensors},
                      config)
        success = True

    def handle_cancel_job(call):
        """Aborts current job."""
        octoprint_api.post('job', "{\"command\": \"cancel\"}")

    def handle_command(call):
        """Sends a command to the printer."""
        json_string = "{\"command\": \""
        json_string += call.data.get(ATTR_COMMAND)
        json_string += "\"}"
        octoprint_api.post('printer/command', json_string)

    def handle_connect(call):
        """Connects to the printer."""
        port = call.data.get(ATTR_PORT)
        baudrate = call.data.get(ATTR_BAUDRATE)
        printer_profile = call.data.get(ATTR_PRINTER_PROFILE)

        json_string = "{\"command\": \"connect\""
        if port is not None:
            json_string += ", \"port\": \"{}\"".format(port)
        if baudrate is not None:
            json_string += ", \"baudrate\": {}".format(baudrate)
        if printer_profile is not None:
            json_string += ", \"printerProfile\": \"{}\"".format(
                printer_profile)
        json_string += "}"

        octoprint_api.post('connection', json_string)

    def handle_disconnect(call):
        """Disconnects from the printer."""
        octoprint_api.post('connection', "{\"command\": \"disconnect\"}")

    def handle_pause_job(call):
        """Pauses current job."""
        octoprint_api.post(
            'job', "{\"command\": \"pause\",\"action\": \"pause\"}")

    def handle_resume_job(call):
        """Resumes current job."""
        octoprint_api.post(
            'job', "{\"command\": \"pause\",\"action\": \"resume\"}")

    def handle_target_temperature(call):
        """Sets the target temperature for a tool or the bed."""
        name = call.data.get(ATTR_NAME)
        temperature = call.data.get(ATTR_TEMPERATURE)

        if name == "bed":
            json_string = "{\"command\": \"target\", \"target\": "
            json_string += str(temperature)
            json_string += "}"
            octoprint_api.post('printer/bed', json_string)
        else:
            json_string = "{\"command\": \"target\",\"targets\": {\""
            json_string += str(name)
            json_string += "\": "
            json_string += str(temperature)
            json_string += "}}"
            octoprint_api.post('printer/tool', json_string)

    hass.services.register(DOMAIN, SERVICE_CANCEL_JOB, handle_cancel_job)
    hass.services.register(DOMAIN, SERVICE_COMMAND, handle_command)
    hass.services.register(DOMAIN, SERVICE_CONNECT, handle_connect)
    hass.services.register(DOMAIN, SERVICE_DISCONNECT, handle_disconnect)
    hass.services.register(DOMAIN, SERVICE_PAUSE_JOB, handle_pause_job)
    hass.services.register(DOMAIN, SERVICE_RESUME_JOB, handle_resume_job)
    hass.services.register(
        DOMAIN, SERVICE_TARGET_TEMPERATURE, handle_target_temperature)

    return success


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
                tools.append('tool' + str(tool_number))
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
        if endpoint == 'job':
            last_time = self.job_last_reading[1]
            if last_time is not None:
                if now - last_time < 30.0:
                    return self.job_last_reading[0]
        elif endpoint == 'printer':
            last_time = self.printer_last_reading[1]
            if last_time is not None:
                if now - last_time < 30.0:
                    return self.printer_last_reading[0]

        url = self.api_url + endpoint
        try:
            response = requests.get(
                url, headers=self.headers, timeout=9)
            response.raise_for_status()
            if endpoint == 'job':
                self.job_last_reading[0] = response.json()
                self.job_last_reading[1] = time.time()
                self.job_available = True
            elif endpoint == 'printer':
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
            if endpoint == 'job':
                log_string = "Endpoint: job " + log_string
                if not self.job_error_logged:
                    _LOGGER.error(log_string)
                    self.job_error_logged = True
                    self.job_available = False
            elif endpoint == 'printer':
                log_string = "Endpoint: printer " + log_string
                if not self.printer_error_logged:
                    _LOGGER.error(log_string)
                    self.printer_error_logged = True
                    self.printer_available = False
            self.available = False
            return None

    def post(self, endpoint, data):
        """Send a post request, and return the response as a dict."""
        # Only query the API at most every 30 seconds
        url = self.api_url + endpoint
        try:
            response = requests.post(
                url, data=data, headers=self.headers, timeout=9)
            response.raise_for_status()
            return response.text
        except Exception as conn_exc:  # pylint: disable=broad-except
            log_string = "Failed to send to OctoPrint.\n" + \
                "Error: %s" % (conn_exc)
            if response is not None:
                log_string += "\n %s" % (response.text)
            _LOGGER.error(log_string)
            return None

    def update(self, endpoint, path):
        """Return the value for sensor_type from the provided endpoint."""
        response = self.get(endpoint)
        if response is not None:
            return get_value_from_json(response, path)
        return response


def get_value_from_json(json_dict, path):
    """Return the value using the path from the JSON result."""
    value = json_dict
    for key in path:
        value = value[key]
    return value
