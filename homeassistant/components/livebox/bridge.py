"""Collect datas information from livebox."""
import logging

from aiosysbus import AIOSysbus
from aiosysbus.exceptions import (
    AuthorizationError,
    InsufficientPermissionsError,
    NotOpenError,
)

from homeassistant import exceptions

from .const import CONF_LAN_TRACKING

_LOGGER = logging.getLogger(__name__)


class BridgeData:
    """Simplification of API calls."""

    def __init__(self, hass, config_entry=None, config_flow_data=None):
        """Init parameters."""
        self._hass = hass
        self.config_entry = config_entry
        if config_entry is not None:
            self.data_config = config_entry.data
        if config_flow_data is not None:
            self.data_config = config_flow_data
        self.api = None

    async def async_connect(self):
        """Connect at livebox."""
        self.api = AIOSysbus(
            username=self.data_config["username"],
            password=self.data_config["password"],
            host=self.data_config["host"],
            port=self.data_config["port"],
        )

        try:
            await self._hass.async_add_executor_job(self.api.connect)
        except AuthorizationError:
            _LOGGER.error("Authentication Required.")
            raise AuthorizationError
        except NotOpenError:
            _LOGGER.error("Cannot Connect.")
            raise NotOpenError
        except Exception as e:
            _LOGGER.error(f"Error unknown {e}")
            raise LiveboxException(e)

        perms = await self._hass.async_add_executor_job(self.api.get_permissions)
        if perms is None:
            _LOGGER.error("Insufficient Permissions.")
            raise InsufficientPermissionsError

    async def async_fetch_datas(self):
        """Fetch datas."""
        return {
            "devices": await self.async_get_devices(),
            "infos": await self.async_get_infos(),
            "status": await self.async_get_status(),
            "dsl_status": await self.async_get_dsl_status(),
            "wifi": await self.async_get_wifi(),
            "nmc": await self.async_get_nmc(),
        }

    async def async_get_devices(self):
        """Get all devices."""
        devices_tracker = {}
        parameters = {
            "expression": {
                "wifi": 'wifi && (edev || hnid) and .PhysAddress!=""',
                "eth": 'eth && (edev || hnid) and .PhysAddress!=""',
            }
        }

        devices = await self._hass.async_add_executor_job(
            self.api.system.get_devices, parameters
        )
        _LOGGER.debug("Devices %s" % (devices is None))
        if devices is not None:
            devices_status_wireless = devices.get("status", {}).get("wifi", {})
            for device in devices_status_wireless:
                if device.get("Key"):
                    devices_tracker.update({device.get("Key"): device})

            if self.config_entry.options.get(CONF_LAN_TRACKING, False):
                devices_status_wired = devices.get("status", {}).get("eth", {})
                for device in devices_status_wired:
                    if device.get("Key"):
                        devices_tracker.update({device.get("Key"): device})

        return devices_tracker

    async def async_get_infos(self):
        """Get router infos."""
        infos = await self._hass.async_add_executor_job(self.api.system.get_deviceinfo)
        if infos:
            return infos.get("status")
        return {}

    async def async_get_status(self):
        """Get status."""
        status = await self._hass.async_add_executor_job(self.api.system.get_WANStatus)
        if status:
            return status.get("data")
        return {}

    async def async_get_dsl_status(self):
        """Get dsl status."""
        parameters = {"mibs": "dsl", "flag": "", "traverse": "down"}
        dsl_status = await self._hass.async_add_executor_job(
            self.api.connection.get_data_MIBS, parameters
        )
        if dsl_status:
            return dsl_status.get("status", {}).get("dsl", {}).get("dsl0")
        return {}

    async def async_get_nmc(self):
        """Get dsl status."""
        nmc = await self._hass.async_add_executor_job(self.api.system.get_nmc)
        if nmc:
            return nmc.get("status")
        return {}

    async def async_get_wifi(self):
        """Get dsl status."""
        wifi = await self._hass.async_add_executor_job(self.api.wifi.get_wifi)
        if wifi:
            return wifi.get("status", {}).get("Enable") == "true"
        return {}

    async def async_set_wifi(self, parameters):
        """Set wifi."""
        await self._hass.async_add_executor_job(self.api.wifi.set_wifi, parameters)

    async def async_reboot(self):
        """Turn on reboot."""
        await self._hass.async_add_executor_job(self.api.system.reboot)


class LiveboxException(exceptions.HomeAssistantError):
    """Base class for Livebox exceptions."""
