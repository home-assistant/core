"""DataUpdateCoordinator for Teltonika."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponseError, ContentTypeError
from teltasync import Teltasync, TeltonikaAuthenticationError, TeltonikaConnectionError
from teltasync.modems import Modems

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import TeltonikaConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class TeltonikaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Teltonika data."""

    device_info: DeviceInfo

    def __init__(
        self,
        hass: HomeAssistant,
        client: Teltasync,
        config_entry: TeltonikaConfigEntry,
        base_url: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Teltonika",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.base_url = base_url

    async def _async_setup(self) -> None:
        """Set up the coordinator - authenticate and fetch device info."""
        try:
            await self.client.get_device_info()
            system_info_response = await self.client.get_system_info()
        except TeltonikaAuthenticationError as err:
            raise ConfigEntryError(f"Authentication failed: {err}") from err
        except (ClientResponseError, ContentTypeError) as err:
            if isinstance(err, ClientResponseError) and err.status in (401, 403):
                raise ConfigEntryError(f"Authentication failed: {err}") from err
            if isinstance(err, ContentTypeError) and err.status == 403:
                raise ConfigEntryError(f"Authentication failed: {err}") from err
            raise ConfigEntryNotReady(f"Failed to connect to device: {err}") from err
        except TeltonikaConnectionError as err:
            raise ConfigEntryNotReady(f"Failed to connect to device: {err}") from err

        # Store device info for use by entities
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, system_info_response.mnf_info.serial)},
            name=system_info_response.static.device_name,
            manufacturer="Teltonika",
            model=system_info_response.static.model,
            sw_version=system_info_response.static.fw_version,
            serial_number=system_info_response.mnf_info.serial,
            configuration_url=self.base_url,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Teltonika device."""
        modems = Modems(self.client.auth)
        try:
            # Get modems data using the teltasync library
            modems_response = await modems.get_status()
        except TeltonikaConnectionError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err

        # Return only modems which are online
        modem_data: dict[str, Any] = {}
        if modems_response.data:
            modem_data.update(
                {
                    modem.id: modem
                    for modem in modems_response.data
                    if Modems.is_online(modem)
                }
            )

        return modem_data
