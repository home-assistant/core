"""DataUpdateCoordinator for the Arris TG2492LG integration."""

import logging
from typing import override

from aiohttp import ClientConnectionError, ClientResponseError
from arris_tg2492lg import ConnectBox, Device
from arris_tg2492lg.exception import InvalidCredentialError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type ArrisConfigEntry = ConfigEntry[ArrisCoordinator]


class ArrisCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Coordinator for fetching connected devices from an Arris TG2492LG router."""

    config_entry: ArrisConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ArrisConfigEntry,
        connect_box: ConnectBox,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.connect_box = connect_box

    @override
    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data from the router."""
        try:
            result = await self.connect_box.async_get_connected_devices()
        except ClientConnectionError as err:
            raise UpdateFailed(f"Error communicating with router: {err}") from err
        except InvalidCredentialError as err:
            raise ConfigEntryAuthFailed("Invalid credentials for router") from err
        except ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed("Invalid credentials for router") from err
            raise UpdateFailed(f"Error communicating with router: {err}") from err

        devices: dict[str, Device] = {}
        for device in result:
            if device.mac and device.online and device.mac not in devices:
                devices[device.mac] = device

        _LOGGER.debug("Arris TG2492LG getConnDevices returned: %s", result)

        return devices
