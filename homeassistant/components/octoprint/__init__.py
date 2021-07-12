"""Support for monitoring OctoPrint 3D printers."""
import logging
import time

from aiohttp.hdrs import CONTENT_TYPE
import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SSL,
    CONTENT_TYPE_JSON,
    PERCENTAGE,
    TEMP_CELSIUS,
    TIME_SECONDS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import slugify as util_slugify

_LOGGER = logging.getLogger(__name__)

CONF_BED = "bed"
CONF_NUMBER_OF_TOOLS = "number_of_tools"

DEFAULT_NAME = "OctoPrint"
DOMAIN = "octoprint"


def has_all_unique_names(value):
    """Validate that printers have an unique name."""
    names = [util_slugify(printer["name"]) for printer in value]
    vol.Schema(vol.Unique())(names)
    return value


def ensure_valid_path(value):
    """Validate the path, ensuring it starts and ends with a /."""
    vol.Schema(cv.string)(value)
    if value[0] != "/":
        value = f"/{value}"
    if value[-1] != "/":
        value += "/"
    return value


BINARY_SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit
    "Printing": ["printer", "state", "printing", None],
    "Printing Error": ["printer", "state", "error", None],
}

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSOR_TYPES)
        ): vol.All(cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit, icon
    "Temperatures": ["printer", "temperature", "*", TEMP_CELSIUS],
    "Current State": ["printer", "state", "text", None, "mdi:printer-3d"],
    "Job Percentage": [
        "job",
        "progress",
        "completion",
        PERCENTAGE,
        "mdi:file-percent",
    ],
    "Time Remaining": [
        "job",
        "progress",
        "printTimeLeft",
        TIME_SECONDS,
        "mdi:clock-end",
    ],
    "Time Elapsed": ["job", "progress", "printTime", TIME_SECONDS, "mdi:clock-start"],
}

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_API_KEY): cv.string,
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_SSL, default=False): cv.boolean,
                        vol.Optional(CONF_PORT, default=80): cv.port,
                        vol.Optional(CONF_PATH, default="/"): ensure_valid_path,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_NUMBER_OF_TOOLS, default=0): cv.positive_int,
                        vol.Optional(CONF_BED, default=False): cv.boolean,
                        vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
                        vol.Optional(
                            CONF_BINARY_SENSORS, default={}
                        ): BINARY_SENSOR_SCHEMA,
                    }
                )
            ],
            has_all_unique_names,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the OctoPrint component."""
    printers = hass.data[DOMAIN] = {}
    success = False

    if DOMAIN not in config:
        # Skip the setup if there is no configuration present
        return True

    for printer in config[DOMAIN]:
        name = printer[CONF_NAME]
        protocol = "https" if printer[CONF_SSL] else "http"
        base_url = (
            f"{protocol}://{printer[CONF_HOST]}:{printer[CONF_PORT]}"
            f"{printer[CONF_PATH]}api/"
        )
        api_key = printer[CONF_API_KEY]
        number_of_tools = printer[CONF_NUMBER_OF_TOOLS]
        bed = printer[CONF_BED]
        try:
            octoprint_api = OctoPrintAPI(base_url, api_key, bed, number_of_tools)
            printers[base_url] = octoprint_api
            octoprint_api.get("printer")
            octoprint_api.get("job")
        except requests.exceptions.RequestException as conn_err:
            _LOGGER.error("Error setting up OctoPrint API: %r", conn_err)
            continue

        sensors = printer[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
        load_platform(
            hass,
            "sensor",
            DOMAIN,
            {"name": name, "base_url": base_url, "sensors": sensors},
            config,
        )
        b_sensors = printer[CONF_BINARY_SENSORS][CONF_MONITORED_CONDITIONS]
        load_platform(
            hass,
            "binary_sensor",
            DOMAIN,
            {"name": name, "base_url": base_url, "sensors": b_sensors},
            config,
        )
        success = True

    return success


class OctoPrintAPI:
    """Simple JSON wrapper for OctoPrint's API."""

    def __init__(self, api_url, key, bed, number_of_tools):
        """Initialize OctoPrint API and set headers needed later."""
        self.api_url = api_url
        self.headers = {CONTENT_TYPE: CONTENT_TYPE_JSON, "X-Api-Key": key}
        self.printer_last_reading = [{}, None]
        self.job_last_reading = [{}, None]
        self.job_available = False
        self.printer_available = False
        self.printer_error_logged = False
        self.available = False
        self.available_error_logged = False
        self.job_error_logged = False
        self.bed = bed
        self.number_of_tools = number_of_tools

    def get_tools(self):
        """Get the list of tools that temperature is monitored on."""
        tools = []
        if self.number_of_tools > 0:
            for tool_number in range(0, self.number_of_tools):
                tools.append(f"tool{tool_number!s}")
        if self.bed:
            tools.append("bed")
        if not self.bed and self.number_of_tools == 0:
            temps = self.printer_last_reading[0].get("temperature")
            if temps is not None:
                tools = temps.keys()
        return tools

    def get(self, endpoint):
        """Send a get request, and return the response as a dict."""
        # Only query the API at most every 30 seconds
        now = time.time()
        if endpoint == "job":
            last_time = self.job_last_reading[1]
            if last_time is not None and now - last_time < 30.0:
                return self.job_last_reading[0]
        elif endpoint == "printer":
            last_time = self.printer_last_reading[1]
            if last_time is not None and now - last_time < 30.0:
                return self.printer_last_reading[0]

        url = self.api_url + endpoint
        try:
            response = requests.get(url, headers=self.headers, timeout=9)
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
                self.available_error_logged = False

            return response.json()

        except requests.ConnectionError as exc_con:
            log_string = f"Failed to connect to Octoprint server. Error: {exc_con}"

            if not self.available_error_logged:
                _LOGGER.error(log_string)
                self.job_available = False
                self.printer_available = False
                self.available_error_logged = True

            return None

        except requests.HTTPError as ex_http:
            status_code = ex_http.response.status_code

            log_string = f"Failed to update OctoPrint status. Error: {ex_http}"
            # Only log the first failure
            if endpoint == "job":
                log_string = f"Endpoint: job {log_string}"
                if not self.job_error_logged:
                    _LOGGER.error(log_string)
                    self.job_error_logged = True
                    self.job_available = False
            elif endpoint == "printer":
                if (
                    status_code == 409
                ):  # octoprint returns HTTP 409 when printer is not connected (and many other states)
                    self.printer_available = False
                else:
                    log_string = f"Endpoint: printer {log_string}"
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

    if tool is not None and sensor_type in json_dict[group][tool]:
        return json_dict[group][tool][sensor_type]

    return None
