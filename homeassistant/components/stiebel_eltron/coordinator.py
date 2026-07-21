"""Data Coordinator base class for the STIEBEL ELTRON heat pumps."""

from datetime import timedelta
import logging
from typing import override

from modbus_connection import ModbusConnection, ModbusError
from pystiebeleltron import ControllerModel
from pystiebeleltron.lwz import LwzStiebelEltronAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_MANUFACTURER, DEFAULT_SCAN_INTERVAL, DOMAIN, UNIT_ID

_LOGGER: logging.Logger = logging.getLogger(__package__)

type StiebelEltronConfigEntry = ConfigEntry[StiebelEltronDataCoordinator]


class StiebelEltronDataCoordinator(DataUpdateCoordinator[None]):
    """Data coordinator base class for stiebel eltron isg."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: StiebelEltronConfigEntry,
        model: ControllerModel,
        connection: ModbusConnection,
        host: str,
    ) -> None:
        """Initialize the StiebelEltronDataCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Stiebel Eltron {model.name}",
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            # The coordinator holds no data of its own (the API client caches
            # the register values), so there is nothing to diff against.
            always_update=True,
        )
        self.api_client = LwzStiebelEltronAPI(connection.for_unit(UNIT_ID))
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            configuration_url=f"http://{host}",
            name=self.name,
            model=model.name,
            model_id=str(model.value),
            manufacturer=ATTR_MANUFACTURER,
        )

    @override
    async def _async_update_data(self) -> None:
        """Fetch the latest data from the source."""
        try:
            await self.api_client.async_update()
        except ModbusError as exception:
            raise UpdateFailed(exception) from exception
