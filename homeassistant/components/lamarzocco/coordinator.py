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
from lmcloud.const import BT_MODEL_PREFIXES
from lmcloud.exceptions import AuthFail, RequestNotSuccessful
from lmcloud.lm_device import LaMarzoccoDevice
from lmcloud.lm_machine import LaMarzoccoMachine

from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_USE_BLUETOOTH, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)
FIRMWARE_UPDATE_INTERVAL = 3600
STATISTICS_UPDATE_INTERVAL = 300

_LOGGER = logging.getLogger(__name__)

_DeviceT = TypeVar("_DeviceT", bound=LaMarzoccoDevice)


class LaMarzoccoUpdateCoordinator(DataUpdateCoordinator[None], Generic[_DeviceT]):
    """Class to handle fetching data from the La Marzocco API centrally."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.local_connection_configured = (
            self.config_entry.data.get(CONF_HOST) is not None
        )

        assert self.config_entry.unique_id
        serial = self.config_entry.unique_id

        cloud_client = LaMarzoccoCloudClient(
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
        )

        # initialize local API
        local_client: LaMarzoccoLocalClient | None = None
        if (host := self.config_entry.data.get(CONF_HOST)) is not None:
            _LOGGER.debug("Initializing local API")
            local_client = LaMarzoccoLocalClient(
                host=host,
                local_bearer=self.config_entry.data[CONF_TOKEN],
                client=get_async_client(self.hass),
            )

        bluetooth_client: LaMarzoccoBluetoothClient | None = None
        self._use_bluetooth = False
        # initialize Bluetooth
        if self.config_entry.options.get(CONF_USE_BLUETOOTH, True):

            def bluetooth_configured() -> bool:
                return self.config_entry.data.get(
                    CONF_MAC, ""
                ) and self.config_entry.data.get(CONF_NAME, "")

            if not bluetooth_configured():
                for discovery_info in async_discovered_service_info(self.hass):
                    if (
                        (name := discovery_info.name)
                        and name.startswith(BT_MODEL_PREFIXES)
                        and name.split("_")[1] == serial
                    ):
                        _LOGGER.debug(
                            "Found Bluetooth device, configuring with Bluetooth"
                        )
                        # found a device, add MAC address to config entry
                        self.hass.config_entries.async_update_entry(
                            self.config_entry,
                            data={
                                **self.config_entry.data,
                                CONF_MAC: discovery_info.address,
                                CONF_NAME: discovery_info.name,
                            },
                        )
                        break

            if bluetooth_configured():
                _LOGGER.debug("Initializing Bluetooth device")
                self._use_bluetooth = True
                bluetooth_client = LaMarzoccoBluetoothClient(
                    username=self.config_entry.data[CONF_USERNAME],
                    serial_number=serial,
                    token=self.config_entry.data[CONF_TOKEN],
                    address_or_ble_device=self.config_entry.data[CONF_MAC],
                )

        self.device = self._init_device(
            model=self.config_entry.data[CONF_MODEL],
            serial_number=serial,
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

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator."""

        super().__init__(hass)

        if self.config_entry.data.get(CONF_HOST) is not None:
            _LOGGER.debug("Init WebSocket in background task")

            self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self.device.websocket_connect(
                    notify_callback=lambda: self.async_set_updated_data(None)
                ),
                name="lm_websocket_task",
            )

    def _init_device(self, *args: Any, **kwargs: Any) -> LaMarzoccoMachine:
        """Initialize the La Marzocco Machine."""
        return LaMarzoccoMachine(*args, **kwargs)
