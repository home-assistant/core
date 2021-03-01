"""Support for monitoring OctoPrint 3D printers."""
from datetime import timedelta
import logging

from pyoctoprintapi import OctoprintClient, PrinterOffline
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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify as util_slugify
import homeassistant.util.dt as dt_util

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


BINARY_SENSOR_TYPES = [
    "Printing",
    "Printing Error",
]

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSOR_TYPES)
        ): vol.All(cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

SENSOR_TYPES = [
    "Temperatures",
    "Current State",
    "Job Percentage",
    "Time Remaining",
    "Time Elapsed",
]

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


async def async_setup(hass, config):
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
            f"{printer[CONF_PATH]}"
        )

        session = async_get_clientsession(hass)
        octoprint = OctoprintClient(
            printer[CONF_HOST],
            session,
            printer[CONF_PORT],
            printer[CONF_SSL],
            printer[CONF_PATH],
        )
        octoprint.set_api_key(printer[CONF_API_KEY])
        coordinator = OctoprintDataUpdateCoordinator(hass, octoprint, base_url, 30)
        await coordinator.async_refresh()

        printers[base_url] = coordinator

        sensors = printer[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
        hass.async_create_task(
            async_load_platform(
                hass,
                "sensor",
                DOMAIN,
                {
                    "name": name,
                    "base_url": base_url,
                    "sensors": sensors,
                    CONF_NUMBER_OF_TOOLS: printer[CONF_NUMBER_OF_TOOLS],
                    CONF_BED: printer[CONF_BED],
                },
                config,
            )
        )
        b_sensors = printer[CONF_BINARY_SENSORS][CONF_MONITORED_CONDITIONS]
        hass.async_create_task(
            async_load_platform(
                hass,
                "binary_sensor",
                DOMAIN,
                {"name": name, "base_url": base_url, "sensors": b_sensors},
                config,
            )
        )
        success = True

    return success


class OctoprintDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Octoprint data."""

    def __init__(
        self,
        hass: HomeAssistant,
        octoprint: OctoprintClient,
        device_id: str,
        interval: int,
    ):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"octoprint-{device_id}",
            update_interval=timedelta(seconds=interval),
        )
        self._octoprint = octoprint
        self.data = {"printer": None, "job": None, "last_read_time": None}

    async def _async_update_data(self):
        """Update data via API."""
        printer = None
        job = await self._octoprint.get_job_info()

        # If octoprint is on, but the printer is disconnected
        # printer will return a 409, so continue using the last
        # reading if there is one
        try:
            printer = await self._octoprint.get_printer_info()
        except PrinterOffline:
            _LOGGER.error("Unable to retrieve printer information: Printer offline")
            if self.data and "printer" in self.data:
                printer = self.data["printer"]

        return {"job": job, "printer": printer, "last_read_time": dt_util.utcnow()}
