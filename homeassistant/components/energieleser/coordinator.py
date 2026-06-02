"""Coordinator for the energieleser integration."""

from datetime import timedelta

from energieleser import (
    DeviceType,
    EnergieleserClient,
    EnergieleserConnectionError,
    EnergieleserDevice,
    EnergieleserError,
    EnergieleserUnknownDeviceError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(seconds=5)

type EnergieleserConfigEntry = ConfigEntry[EnergieleserCoordinator]


class EnergieleserCoordinator(DataUpdateCoordinator[EnergieleserDevice]):
    """Coordinator that polls a single energieleser device."""

    config_entry: EnergieleserConfigEntry
    device_id: str
    device_type: DeviceType

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EnergieleserConfigEntry,
        client: EnergieleserClient,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device_id = config_entry.data[CONF_DEVICE_ID]

    async def _async_update_data(self) -> EnergieleserDevice:
        """Fetch data from the energieleser device API."""
        try:
            device = await self.client.get_device()
        except EnergieleserUnknownDeviceError as err:
            raise UpdateFailed(
                f"Unknown or unsupported device type for {self.device_id}: {err}"
            ) from err
        except EnergieleserConnectionError as err:
            raise UpdateFailed(
                f"Cannot connect to energieleser device {self.device_id}: {err}"
            ) from err
        except EnergieleserError as err:
            raise UpdateFailed(
                f"Error communicating with energieleser device {self.device_id}: {err}"
            ) from err
        self.device_type = device.device_type
        return device
