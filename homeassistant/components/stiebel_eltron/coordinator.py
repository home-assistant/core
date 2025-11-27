"""Data Coordinator base class for the STIEBEL ELTRON heat pumps."""

from datetime import timedelta
import logging

from pymodbus.exceptions import ModbusException
from pystiebeleltron import ControllerModel
from pystiebeleltron.lwz import LwzStiebelEltronAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_MANUFACTURER, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)

type StiebelEltronConfigEntry = ConfigEntry[StiebelEltronDataCoordinator]


class StiebelEltronDataCoordinator(DataUpdateCoordinator[None]):
    """Data coordinator base class for stiebel eltron isg."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: StiebelEltronConfigEntry,
        model: ControllerModel,
        host: str,
        port: int,
    ) -> None:
        """Initialize the StiebelEltronDataCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Stiebel Eltron {model.name}",
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=True,
        )
        self._model = model
        self.api_client = LwzStiebelEltronAPI(host=host, port=port)
        self.platforms: list = []
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            configuration_url=f"http://{self.host}",
            name=self.name,
            model=model.name,
            model_id=str(model.value),
            manufacturer=ATTR_MANUFACTURER,
        )

    async def close(self) -> None:
        """Disconnect client."""
        _LOGGER.debug("Closing connection to %s", self.host)
        await self.api_client.close()

    async def connect(self) -> None:
        """Connect client."""
        _LOGGER.debug("Connecting to %s", self.host)
        await self.api_client.connect()

    @property
    def is_connected(self) -> bool:
        """Check modbus client connection status."""
        if self.api_client is None:
            return False
        return self.api_client.is_connected

    @property
    def host(self) -> str:
        """Return the host address of the Stiebel Eltron ISG."""
        return self.api_client.host

    @property
    def model(self) -> str:
        """Return the controller model name of the Stiebel Eltron ISG."""
        return self._model.name

    async def _async_update_data(self) -> None:
        """Fetch the latest data from the source."""
        try:
            if not self.api_client.is_connected:
                await self.api_client.connect()
            await self.api_client.async_update()
        except ModbusException as exception:
            raise UpdateFailed(exception) from exception
