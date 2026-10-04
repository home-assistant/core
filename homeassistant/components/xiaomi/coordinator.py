"""DataUpdateCoordinator for the Xiaomi integration."""

import logging
from typing import Any, TypedDict, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL
from .router import (
    XiaomiAuthError,
    XiaomiClient,
    XiaomiConnectionError,
    XiaomiTimeoutError,
)

_LOGGER = logging.getLogger(__name__)


def _is_online(online: Any) -> bool:
    """Return true if the router reports the device as online."""
    try:
        return int(online) == 1
    except TypeError, ValueError:
        return False


def _extract_ip(ip_value: Any) -> str | None:
    """Extract the first usable IP address from the router's IP record list."""
    if isinstance(ip_value, str):
        return ip_value or None
    if isinstance(ip_value, list):
        for record in ip_value:
            if (
                isinstance(record, dict)
                and isinstance(ip := record.get("ip"), str)
                and ip
            ):
                return ip
    return None


class XiaomiDeviceInfo(TypedDict, total=False):
    """A device connected to a Xiaomi Mi router."""

    name: str
    ip: str


type XiaomiConfigEntry = ConfigEntry[XiaomiCoordinator]


class XiaomiCoordinator(DataUpdateCoordinator[dict[str, XiaomiDeviceInfo]]):
    """Coordinator for fetching connected devices from a Xiaomi Mi router."""

    config_entry: XiaomiConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: XiaomiConfigEntry,
        client: XiaomiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> dict[str, XiaomiDeviceInfo]:
        """Fetch data from the router."""
        host = self.config_entry.data[CONF_HOST]
        try:
            result = await self.hass.async_add_executor_job(self.client.get_device_list)
        except XiaomiTimeoutError as err:
            raise UpdateFailed(
                f"Timed out communicating with router at {host}"
            ) from err
        except XiaomiConnectionError as err:
            raise UpdateFailed(f"Error communicating with router at {host}") from err
        except XiaomiAuthError as err:
            raise ConfigEntryAuthFailed("Invalid credentials for router") from err

        _LOGGER.debug("Xiaomi get_device_list returned: %s", result)

        devices: dict[str, XiaomiDeviceInfo] = {}
        for device in result:
            mac = device.get("mac")
            if (
                not isinstance(mac, str)
                or not mac
                or not _is_online(device.get("online"))
            ):
                continue
            # MAC addresses are case-insensitive; normalize so a casing
            # change between polls does not create a second entity.
            mac = mac.lower()
            if mac in devices:
                continue
            device_info: XiaomiDeviceInfo = {}
            if isinstance(name := device.get("name"), str):
                device_info["name"] = name
            if ip := _extract_ip(device.get("ip")):
                device_info["ip"] = ip
            devices[mac] = device_info
        return devices
