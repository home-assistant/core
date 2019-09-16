"""Orange Livebox."""
import logging
from datetime import timedelta
import voluptuous as vol

from aiosysbus import Sysbus
from aiosysbus.exceptions import HttpRequestError, AuthorizationError

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.config_entries import SOURCE_IMPORT

from .const import (
    DOMAIN,
    COMPONENTS,
    DATA_LIVEBOX,
    DEFAULT_USERNAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                # Validate as IP address and then convert back to a string.
                vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup(hass, config):
    """Load configuration for Livebox component."""

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        livebox_config = config[DOMAIN]
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=livebox_config
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Livebox as config entry."""

    box_data = LiveboxData(config_entry)
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_LIVEBOX] = box_data

    config = await box_data.async_infos()
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.data["id"])},
        manufacturer=config["Manufacturer"],
        name=config["ProductClass"],
        model=config["ModelName"],
        sw_version=config["SoftwareVersion"],
    )

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_unload(config_entry, component)
        )

    return True


class LiveboxData:
    """Collect datas information from livebox."""

    def __init__(self, config_entry):
        """Init datas from router."""

        self._box = Sysbus()
        self._entry = config_entry

    async def async_devices(self, device=None):
        """Get devices datas."""

        parameters = {"parameters": {"expression": {"wifi": "wifi"}}}
        if device is not None:
            parameters = {
                "parameters": {
                    "expression": {
                        "wifi": 'wifi and .PhysAddress=="' + device["PhysAddress"] + '"'
                    }
                }
            }
        box = await self.async_conn()
        devices = await box.system.get_devices(parameters)
        if devices.get("status", {}).get("wifi", {}):
            return devices["status"]["wifi"]
        return None

    async def async_infos(self):
        """Get infos."""

        box = await self.async_conn()
        infos = await box.system.get_deviceinfo()
        if infos.get("status", {}):
            return infos["status"]
        return None

    async def async_status(self):
        """Get status."""

        box = await self.async_conn()
        status = await box.system.get_WANStatus()
        if status.get("data", {}):
            return status["data"]
        return None

    async def async_dsl_status(self):
        """Get dsl status."""

        box = await self.async_conn()
        parameters = {"parameters": {"mibs": "dsl", "flag": "", "traverse": "down"}}
        dsl_status = await box.connection.get_data_MIBS(parameters)
        if dsl_status.get("status", {}).get("dsl", {}).get("dsl0", {}):
            return dsl_status["status"]["dsl"]["dsl0"]
        return None

    async def async_conn(self):
        """Connect at the livebox router."""

        try:
            await self._box.open(
                host=self._entry.data["host"],
                port=self._entry.data["port"],
                username=self._entry.data["username"],
                password=self._entry.data["password"],
            )
            if await self._box.get_permissions():  # check connection successful
                return self._box

        except AuthorizationError:
            _LOGGER.error("User or password incorrect")
            raise
        except HttpRequestError:
            _LOGGER.error("Http Request error to Livebox")
            raise
