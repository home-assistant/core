"""Collect datas information from livebox."""
import logging

_LOGGER = logging.getLogger(__name__)


class BridgeData:
    """Simplification of API calls."""

    def __init__(self, session, config_entry):
        """Init parameters."""
        self._entry = config_entry
        self._session = session

    async def async_get_devices(self):
        """Get all devices."""
        parameters = {
            "parameters": {
                "expression": {
                    "wifi": 'wifi && (edev || hnid) and .PhysAddress!=""',
                    "eth": 'eth && (edev || hnid) and .PhysAddress!=""',
                }
            }
        }
        devices = await self._session.system.get_devices(parameters)
        if devices is not None:
            devices_status_wireless = devices.get("status", {}).get("wifi", {})
            devices_status_wired = devices.get("status", {}).get("eth", {})
            if self._entry.options.get("lan_tracking", False):
                return devices_status_wireless + devices_status_wired
            return devices_status_wireless
        return

    async def async_get_device(self, unique_id):
        """Get device."""
        parameters = {"parameters": {"expression": f'.PhysAddress=="{unique_id}"'}}
        device = await self._session.system.get_devices(parameters)
        if device is not None:
            device_status = device.get("status", [])
            if len(device_status) == 1:
                return device_status.pop()
        return

    async def async_get_infos(self):
        """Get router infos."""
        infos = await self._session.system.get_deviceinfo()
        if infos is not None:
            return infos.get("status", {})
        return

    async def async_get_status(self):
        """Get status."""
        status = await self._session.system.get_WANStatus()
        if status is not None:
            return status.get("data", {})
        return

    async def async_get_dsl_status(self):
        """Get dsl status."""
        parameters = {"parameters": {"mibs": "dsl", "flag": "", "traverse": "down"}}
        dsl_status = await self._session.connection.get_data_MIBS(parameters)
        if dsl_status is not None:
            return dsl_status.get("status", {}).get("dsl", {}).get("dsl0", {})
        return
