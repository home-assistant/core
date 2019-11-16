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
    DATA_LIVEBOX_UNSUB,
    DATA__LIVEBOX_DEVICES,
    DEFAULT_USERNAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    CONF_LAN_TRACKING,
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
                vol.Required(CONF_LAN_TRACKING, default=False): cv.boolean,
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
    hass.data[DOMAIN][DATA_LIVEBOX_UNSUB] = {}
    hass.data[DOMAIN][DATA__LIVEBOX_DEVICES] = set()

    config = await box_data.async_infos()
    if config:
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

    return False


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

        parameters = {
            "parameters": {
                "expression": {"wifi": "wifi", "eth": 'eth and .DeviceType!=""'}
            }
        }
        lan_tracking = self._entry.options.get("lan_tracking", False)

        if device is not None:
            parameters = {
                "parameters": {
                    "expression": {
                        "wifi": 'wifi and .PhysAddress=="'
                        + device["PhysAddress"]
                        + '"',
                        "eth": 'eth and .PhysAddress=="' + device["PhysAddress"] + '"',
                    }
                }
            }
        try:
            await self.async_conn()
        except AuthorizationError:
            _LOGGER.error("Connection Error or permission refused")
            return None
        except Exception:
            _LOGGER.error("Connexion Error")
            return None

        devices = await self._box.system.get_devices(parameters)
        device_wifi = devices.get("status", {}).get("wifi", {})
        device_eth = devices.get("status", {}).get("eth", {})
        if lan_tracking:
            return device_wifi + device_eth
        return device_wifi

    async def async_infos(self):
        """Get infos."""

        try:
            await self.async_conn()
        except AuthorizationError:
            _LOGGER.error("Connection Error or permission refused")
            return None
        except Exception:
            _LOGGER.error("Connexion Error")
            return None

        infos = await self._box.system.get_deviceinfo()

        return infos.get("status", {})

    async def async_status(self):
        """Get status."""

        try:
            await self.async_conn()
        except AuthorizationError:
            _LOGGER.error("Connection Error or permission refused")
            return None
        except Exception:
            _LOGGER.error("Connexion Error")
            return None

        status = await self._box.system.get_WANStatus()

        return status.get("data", {})

    async def async_dsl_status(self):
        """Get dsl status."""

        try:
            await self.async_conn()
        except AuthorizationError:
            _LOGGER.error("Connection Error or permission refused")
            return None
        except Exception:
            _LOGGER.error("Connexion Error")
            return None

        parameters = {"parameters": {"mibs": "dsl", "flag": "", "traverse": "down"}}
        dsl_status = await self._box.connection.get_data_MIBS(parameters)

        return dsl_status.get("status", {}).get("dsl", {}).get("dsl0", {})

    async def async_conn(self):
        """Connect at the livebox router."""

        try:
            await self._box.open(
                host=self._entry.data["host"],
                port=self._entry.data["port"],
                username=self._entry.data["username"],
                password=self._entry.data["password"],
            )
            return await self._box.get_permissions()

        except AuthorizationError:
            _LOGGER.error("User or password incorrect")
            raise
        except HttpRequestError:
            _LOGGER.error("Http Request error to Livebox")
            raise
