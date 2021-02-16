"""Support for monitoring OctoPrint 3D printers."""
import asyncio
from datetime import timedelta
import logging

from pyoctoprintapi import OctoprintClient, PrinterOffline
import voluptuous as vol

<<<<<<< HEAD
=======
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
>>>>>>> 80d7f71a87... Add config flow for octoprint
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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify as util_slugify
import homeassistant.util.dt as dt_util

from .const import CONF_BED, CONF_NUMBER_OF_TOOLS, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


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


PLATFORMS = ["binary_sensor", "sensor"]

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


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the OctoPrint component."""
    if DOMAIN not in config:
        return True

    domain_config = config[DOMAIN]

    for conf in domain_config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_API_KEY: conf[CONF_API_KEY],
                    CONF_HOST: conf[CONF_HOST],
                    CONF_NAME: conf[CONF_NAME],
                    CONF_PATH: conf[CONF_PATH],
                    CONF_PORT: conf[CONF_PORT],
                    CONF_SSL: conf[CONF_SSL],
                },
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up OctoPrint from a config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    websession = async_get_clientsession(hass)
    client = OctoprintClient(
        entry.data[CONF_HOST],
        websession,
        entry.data[CONF_PORT],
        entry.data[CONF_SSL],
        entry.data[CONF_PATH],
    )

    client.set_api_key(entry.data[CONF_API_KEY])

    tracking_info = await client.get_tracking_info()

    coordinator = OctoprintDataUpdateCoordinator(
        hass, client, tracking_info.unique_id, 30
    )

    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "device_id": tracking_info.unique_id,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


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
