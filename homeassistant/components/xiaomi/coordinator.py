"""DataUpdateCoordinator for the Xiaomi integration."""

import logging
from typing import TypedDict, override

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
            if mac and mac not in devices and int(device.get("online", "0")) == 1:
                device_info: XiaomiDeviceInfo = {}
                for key in ("name", "ip"):
                    if key in device:
                        device_info[key] = device[key]
                devices[mac] = device_info
        return devices
