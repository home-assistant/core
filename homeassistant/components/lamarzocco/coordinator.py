"""Coordinator for La Marzocco API."""

from abc import abstractmethod
from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from time import time
from typing import Any, Generic, TypeVar

from lmcloud.client_bluetooth import LaMarzoccoBluetoothClient
from lmcloud.client_cloud import LaMarzoccoCloudClient
from lmcloud.client_local import LaMarzoccoLocalClient
from lmcloud.exceptions import AuthFail, RequestNotSuccessful
from lmcloud.lm_device import LaMarzoccoDevice
from lmcloud.lm_machine import LaMarzoccoMachine

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)
FIRMWARE_UPDATE_INTERVAL = 3600
STATISTICS_UPDATE_INTERVAL = 300

_LOGGER = logging.getLogger(__name__)

_DeviceT = TypeVar("_DeviceT", bound=LaMarzoccoDevice)


class LaMarzoccoUpdateCoordinator(DataUpdateCoordinator[None], Generic[_DeviceT]):
    """Class to handle fetching data from the La Marzocco API centrally."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        cloud_client: LaMarzoccoCloudClient,
        local_client: LaMarzoccoLocalClient | None,
        bluetooth_client: LaMarzoccoBluetoothClient | None,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.local_connection_configured = local_client is not None

        assert self.config_entry.unique_id
        self.device = self._init_device(
            model=self.config_entry.data[CONF_MODEL],
            serial_number=self.config_entry.unique_id,
            name=self.config_entry.data[CONF_NAME],
            cloud_client=cloud_client,
            local_client=local_client,
            bluetooth_client=bluetooth_client,
        )

        self._last_firmware_data_update: float | None = None
        self._last_statistics_data_update: float | None = None

    @abstractmethod
    def _init_device(*args: Any, **kwargs: Any) -> _DeviceT:
        """Initialize the La Marzocco Device."""

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self._async_handle_request(self.device.get_config)

        if (
            self._last_firmware_data_update is None
            or (self._last_firmware_data_update + FIRMWARE_UPDATE_INTERVAL) < time()
        ):
            await self._async_handle_request(self.device.get_firmware)
            self._last_firmware_data_update = time()

        if (
            self._last_statistics_data_update is None
            or (self._last_statistics_data_update + STATISTICS_UPDATE_INTERVAL) < time()
        ):
            await self._async_handle_request(self.device.get_statistics)
            self._last_statistics_data_update = time()

        _LOGGER.debug("Current status: %s", str(self.device.config))

    async def _async_handle_request(
        self, func: Callable[[], Coroutine[None, None, None]]
    ) -> None:
        try:
            await func()
        except AuthFail as ex:
            msg = "Authentication failed."
            _LOGGER.debug(msg, exc_info=True)
            raise ConfigEntryAuthFailed(msg) from ex
        except RequestNotSuccessful as ex:
            _LOGGER.debug(ex, exc_info=True)
            raise UpdateFailed("Querying API failed. Error: %s" % ex) from ex


class LaMarzoccoMachineUpdateCoordinator(
    LaMarzoccoUpdateCoordinator[LaMarzoccoMachine]
):
    """Class to handle fetching data from the La Marzocco API for a machine."""

    def __init__(
        self,
        hass: HomeAssistant,
        cloud_client: LaMarzoccoCloudClient,
        local_client: LaMarzoccoLocalClient | None,
        bluetooth_client: LaMarzoccoBluetoothClient | None,
    ) -> None:
        """Initialize coordinator."""

        super().__init__(hass, cloud_client, local_client, bluetooth_client)

        if local_client is not None:
            _LOGGER.debug("Init WebSocket in background task")

            self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self.device.websocket_connect(
                    notify_callback=lambda: self.async_set_updated_data(None)
                ),
                name="lm_websocket_task",
            )

            async def websocket_close(_: Any | None = None) -> None:
                if local_client.websocket is not None and local_client.websocket.open:
                    local_client.terminating = True
                    await local_client.websocket.close()

            self.config_entry.async_on_unload(
                hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, websocket_close)
            )
            self.config_entry.async_on_unload(websocket_close)

    def _init_device(self, *args: Any, **kwargs: Any) -> LaMarzoccoMachine:
        """Initialize the La Marzocco Machine."""
        return LaMarzoccoMachine(*args, **kwargs)
