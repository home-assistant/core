"""Support for monitoring OctoPrint 3D printers."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import cast

from pyoctoprintapi import ApiError, OctoprintClient, PrinterOffline
from pyoctoprintapi.exceptions import UnauthorizedException
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
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
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify as util_slugify
import homeassistant.util.dt as dt_util

from .const import DOMAIN

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


PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CAMERA, Platform.SENSOR]
DEFAULT_NAME = "OctoPrint"
CONF_NUMBER_OF_TOOLS = "number_of_tools"
CONF_BED = "bed"

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
    vol.All(
        cv.deprecated(DOMAIN),
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
                            # Following values are not longer used in the configuration of the integration
                            # and are here for historical purposes
                            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                            vol.Optional(
                                CONF_NUMBER_OF_TOOLS, default=0
                            ): cv.positive_int,
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
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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
                    CONF_PATH: conf[CONF_PATH],
                    CONF_PORT: conf[CONF_PORT],
                    CONF_SSL: conf[CONF_SSL],
                },
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OctoPrint from a config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if CONF_VERIFY_SSL not in entry.data:
        data = {**entry.data, CONF_VERIFY_SSL: True}
        hass.config_entries.async_update_entry(entry, data=data)

    verify_ssl = entry.data[CONF_VERIFY_SSL]
    websession = async_get_clientsession(hass, verify_ssl=verify_ssl)
    client = OctoprintClient(
        entry.data[CONF_HOST],
        websession,
        entry.data[CONF_PORT],
        entry.data[CONF_SSL],
        entry.data[CONF_PATH],
    )

    client.set_api_key(entry.data[CONF_API_KEY])

    coordinator = OctoprintDataUpdateCoordinator(hass, client, entry, 30)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class OctoprintDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Octoprint data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        octoprint: OctoprintClient,
        config_entry: ConfigEntry,
        interval: int,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"octoprint-{config_entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )
        self.config_entry = config_entry
        self._octoprint = octoprint
        self._printer_offline = False
        self.data = {"printer": None, "job": None, "last_read_time": None}

    async def _async_update_data(self):
        """Update data via API."""
        printer = None
        try:
            job = await self._octoprint.get_job_info()
        except UnauthorizedException as err:
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(err) from err

        # If octoprint is on, but the printer is disconnected
        # printer will return a 409, so continue using the last
        # reading if there is one
        try:
            printer = await self._octoprint.get_printer_info()
        except PrinterOffline:
            if not self._printer_offline:
                _LOGGER.debug("Unable to retrieve printer information: Printer offline")
                self._printer_offline = True
        except UnauthorizedException as err:
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(err) from err
        else:
            self._printer_offline = False

        return {"job": job, "printer": printer, "last_read_time": dt_util.utcnow()}

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        unique_id = cast(str, self.config_entry.unique_id)
        configuration_url = URL.build(
            scheme=self.config_entry.data[CONF_SSL] and "https" or "http",
            host=self.config_entry.data[CONF_HOST],
            port=self.config_entry.data[CONF_PORT],
            path=self.config_entry.data[CONF_PATH],
        )

        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="OctoPrint",
            name="OctoPrint",
            configuration_url=str(configuration_url),
        )
