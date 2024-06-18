"""Coordinator for La Marzocco API."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from time import time
from typing import Any

from lmcloud.client_bluetooth import LaMarzoccoBluetoothClient
from lmcloud.client_cloud import LaMarzoccoCloudClient
from lmcloud.client_local import LaMarzoccoLocalClient
from lmcloud.exceptions import AuthFail, RequestNotSuccessful
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


class LaMarzoccoUpdateCoordinator(DataUpdateCoordinator[None]):
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
        self.device = LaMarzoccoMachine(
            model=self.config_entry.data[CONF_MODEL],
            serial_number=self.config_entry.unique_id,
            name=self.config_entry.data[CONF_NAME],
            cloud_client=cloud_client,
            local_client=local_client,
            bluetooth_client=bluetooth_client,
        )

        self._last_firmware_data_update: float | None = None
        self._last_statistics_data_update: float | None = None
        self._local_client = local_client

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        if self._local_client is not None:
            _LOGGER.debug("Init WebSocket in background task")

            self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self.device.websocket_connect(
                    notify_callback=lambda: self.async_set_updated_data(None)
                ),
                name="lm_websocket_task",
            )

            async def websocket_close(_: Any | None = None) -> None:
                if (
                    self._local_client is not None
                    and self._local_client.websocket is not None
                    and self._local_client.websocket.open
                ):
                    self._local_client.terminating = True
                    await self._local_client.websocket.close()

            self.config_entry.async_on_unload(
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, websocket_close
                )
            )
            self.config_entry.async_on_unload(websocket_close)

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

    async def _async_handle_request[**_P](
        self,
        func: Callable[_P, Coroutine[None, None, None]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        try:
            await func()
        except AuthFail as ex:
            msg = "Authentication failed."
            _LOGGER.debug(msg, exc_info=True)
            raise ConfigEntryAuthFailed(msg) from ex
        except RequestNotSuccessful as ex:
            _LOGGER.debug(ex, exc_info=True)
            raise UpdateFailed(f"Querying API failed. Error: {ex}") from ex
