"""Orange Livebox."""
import logging
from datetime import timedelta
import voluptuous as vol

from aiosysbus import Sysbus
from aiosysbus.exceptions import HttpRequestError, AuthorizationError

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN, DEFAULT_USERNAME, DEFAULT_HOST, DEFAULT_PORT

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
                DOMAIN, context={"source": config.SOURCE_IMPORT}, data=livebox_config
            )
        )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Livebox as config entry."""

    ld = LiveboxData(config_entry)
    hass.data[DOMAIN] = {}

    config = await ld.async_infos()
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.data["id"])},
        manufacturer=config["Manufacturer"],
        name=config["ProductClass"],
        model=config["ModelName"],
        sw_version=config["SoftwareVersion"],
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "device_tracker")
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(config_entry, "binary_sensor")
    await hass.config_entries.async_forward_entry_unload(config_entry, "device_tracker")
    return True


class LiveboxData:
    """Collect datas information from livebox."""

    def __init__(self, config_entry):
        """Init datas from router."""

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
        devices = (await box.system.get_devices(parameters))["status"]["wifi"]

        return devices

    async def async_infos(self):
        """Get infos."""

        box = await self.async_conn()
        infos = (await box.system.get_deviceinfo())["status"]

        return infos

    async def async_status(self):
        """Get status."""

        box = await self.async_conn()
        status = (await box.system.get_WANStatus())["data"]

        return status

    async def async_dsl_status(self):
        """Get dsl status."""

        box = await self.async_conn()
        parameters = {"parameters": {"mibs": "dsl", "flag": "", "traverse": "down"}}
        dsl_status = (await box.connection.get_data_MIBS(parameters))["status"]["dsl"][
            "dsl0"
        ]

        return dsl_status

    async def async_conn(self):
        """Connect at the livebox router."""

        box = Sysbus()
        try:
            await box.open(
                host=self._entry.data["host"],
                port=self._entry.data["port"],
                username=self._entry.data["username"],
                password=self._entry.data["password"],
            )
            return box

        except AuthorizationError:
            _LOGGER.error("User or password incorrect")
            return False
        except HttpRequestError:
            _LOGGER.error("Http Request error to Livebox")
            return False
