"""DataUpdateCoordinator for IOmeter."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from iometer import IOmeterClient, IOmeterConnectionError, Reading, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)

type IOmeterConfigEntry = ConfigEntry[IOMeterCoordinator]


@dataclass
class IOmeterData:
    """Class for data update."""

    reading: Reading
    status: Status


class IOMeterCoordinator(DataUpdateCoordinator[IOmeterData]):
    """Class to manage fetching IOmeter data."""

    config_entry: IOmeterConfigEntry
    client: IOmeterClient
    current_fw_version: str = ""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: IOmeterConfigEntry,
        client: IOmeterClient,
    ) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.identifier = config_entry.entry_id

    async def _async_update_data(self) -> IOmeterData:
        """Update data async."""
        try:
            reading = await self.client.get_current_reading()
            status = await self.client.get_current_status()
        except IOmeterConnectionError as error:
            raise UpdateFailed(f"Error communicating with IOmeter: {error}") from error

        fw_version = f"{status.device.core.version}/{status.device.bridge.version}"
        if self.current_fw_version and fw_version != self.current_fw_version:
            device_registry = dr.async_get(self.hass)
            device_entry = device_registry.async_get_device(
                identifiers={(DOMAIN, status.device.id)}
            )
            assert device_entry
            device_registry.async_update_device(
                device_entry.id,
                sw_version=fw_version,
            )
        self.current_fw_version = fw_version

        return IOmeterData(reading=reading, status=status)
