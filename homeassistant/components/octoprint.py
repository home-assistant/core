"""
Support for monitoring OctoPrint 3D printers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/octoprint/
"""
import asyncio
import logging
import time
from threading import Lock
from typing import TypeVar, Union, Sequence

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL, \
    CONF_NAME

REQUIREMENTS = ['octoclient==0.2.dev1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'octoprint'
ENTITY_ID_FORMAT = 'octoprint.{}'
DEFAULT_NAME = 'octoprint'
DATA_OCTOPRINT = 'data_octoprint'
CONF_NUMBER_OF_TOOLS = 'number_of_tools'
CONF_BED = 'bed'

# pylint: disable=invalid-name
T = TypeVar('T')


# pylint: enable=invalid-name


# This version of ensure_list interprets an empty dict as no value
def ensure_list(value: Union[T, Sequence[T]]) -> Sequence[T]:
    """Wrap value in list if it is not one."""
    if value is None or (isinstance(value, dict) and not value):
        return []
    return value if isinstance(value, list) else [value]


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(ensure_list, [vol.Schema({
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.string,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NUMBER_OF_TOOLS, default=0): cv.positive_int,
        vol.Optional(CONF_BED, default=False): cv.boolean
    })])
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the OctoPrint component."""
    if DOMAIN not in hass.data:
        octoprints = hass.data[DOMAIN] = {}

    @asyncio.coroutine
    def async_setup_octoprint(octo_config):
        """Set up an Octoprint service."""
        from octoclient import OctoClient

        name = octo_config[CONF_NAME]
        _LOGGER.debug("Configuring Octoprint %s", octo_config[CONF_NAME])

        schema = 'http'
        if CONF_SSL in octo_config:
            if octo_config[CONF_SSL] is True:
                schema = 'https'

        if CONF_PORT in octo_config:
            if octo_config[CONF_HOST].find('/'):
                host = octo_config[CONF_HOST].split('/', 1)[0]
                path = octo_config[CONF_HOST].split('/', 1)[1]
            else:
                host = octo_config[CONF_HOST]
                path = ''
            url = '{}:{}/{}'.format(
                host,
                octo_config[CONF_PORT],
                path
            )
        else:
            url = '{}'.format(octo_config[CONF_HOST])

        base_url = '{}://{}'.format(schema, url)

        try:
            octoprint = OctoClient(url=base_url, apikey=octo_config[CONF_API_KEY])
            octoprint_api = OctoprintHandle(name, octoprint, octo_config[CONF_NUMBER_OF_TOOLS], octo_config[CONF_BED])
            octoprint_api.get("printer")
            octoprint_api.get("job_info")
            octoprints[name] = octoprint_api
            _LOGGER.debug("Setup Octoprint {}".format(octoprints[name]))
        except Exception as e:
            _LOGGER.error(
                "Error setting up OctoPrint {} API: {}".format(
                    name,
                    str(e)
                )
            )

    tasks = [async_setup_octoprint(conf) for conf in config[DOMAIN]]
    if tasks:
        yield from asyncio.wait(tasks, loop=hass.loop)

    _LOGGER.info("Finished setting up Octoprint %r", hass.data[DOMAIN])
    return True


class OctoprintHandle:
    """Keep the Octoprint instance in one place and centralize the update."""

    def __init__(self, name, octoprint, number_of_tools=0, bed=0, scan_interval=30):
        """Initialize the Octoprint Handle."""
        self.name = name
        self.octoprint = octoprint
        self.printer_last_reading = [{}, 0]
        self.job_info_last_reading = [{}, 0]
        self.scan_interval = scan_interval
        self.mutex = Lock()
        self.job_info_available = False
        self.printer_available = False
        self.printer_error_logged = False
        self.job_info_error_logged = False
        self.bed = bed
        self.number_of_tools = number_of_tools

    def get(self, endpoint):
        """Pull the latest data from Octoprint."""
        # Acquire mutex to prevent simultaneous update from multiple threads
        with self.mutex:
            status = self._update_status(endpoint)

        return status

    @property
    def available(self):
        return self.printer_available and self.job_info_available

    def _update_status(self, status_type):
        now = time.time()

        # Only update every update_interval
        last_reading = getattr(self, "{}_last_reading".format(status_type))
        if (now - last_reading[1]) >= self.scan_interval:
            _LOGGER.debug("Updating {} status".format(status_type))
            try:
                last_reading[1] = now
                last_reading[0] = getattr(self.octoprint, status_type)()
                setattr(self, "{}_last_reading".format(status_type), last_reading)
                setattr(self, "{}_error_logged".format(status_type), False)
                setattr(self, "{}_available".format(status_type), True)
                return last_reading[0]
            except Exception as e:
                last_reading[1] = now
                setattr(self, "{}_last_reading".format(status_type), last_reading)
                setattr(self, "{}_error_logged".format(status_type), True)
                setattr(self, "{}_available".format(status_type), False)
                _LOGGER.error("Error communicating with Octoprint {}. {}".format(self.name, str(e)))

        return last_reading[0]

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
        if tool in json_dict[group]:
            if sensor_type in json_dict[group][tool]:
                return json_dict[group][tool][sensor_type]

    return None
