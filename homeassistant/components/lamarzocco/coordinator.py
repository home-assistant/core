"""Coordinator for La Marzocco API."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging

from bleak.backends.device import BLEDevice
from lmcloud import LMCloud as LaMarzoccoClient
from lmcloud.const import BT_MODEL_NAMES
from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_MACHINE, CONF_USE_BLUETOOTH, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


NAME_PREFIXES = tuple(BT_MODEL_NAMES)


class LaMarzoccoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to handle fetching data from the La Marzocco API centrally."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.lm = LaMarzoccoClient(
            callback_websocket_notify=self.async_update_listeners,
        )
        self.local_connection_configured = (
            self.config_entry.data.get(CONF_HOST) is not None
        )
        self._use_bluetooth = False

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        if not self.lm.initialized:
            await self._async_init_client()

        await self._async_handle_request(
            self.lm.update_local_machine_status, force_update=True
        )

        _LOGGER.debug("Current status: %s", str(self.lm.current_status))

    async def _async_init_client(self) -> None:
        """Initialize the La Marzocco Client."""

        # Initialize cloud API
        _LOGGER.debug("Initializing Cloud API")
        await self._async_handle_request(
            self.lm.init_cloud_api,
            credentials=self.config_entry.data,
            machine_serial=self.config_entry.data[CONF_MACHINE],
        )
        _LOGGER.debug("Model name: %s", self.lm.model_name)

        # initialize local API
        if (host := self.config_entry.data.get(CONF_HOST)) is not None:
            _LOGGER.debug("Initializing local API")
            await self.lm.init_local_api(
                host=host,
                client=get_async_client(self.hass),
            )

            _LOGGER.debug("Init WebSocket in Background Task")

            self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self.lm.lm_local_api.websocket_connect(
                    callback=self.lm.on_websocket_message_received,
                    use_sigterm_handler=False,
                ),
                name="lm_websocket_task",
            )

        # initialize Bluetooth
        if self.config_entry.options.get(CONF_USE_BLUETOOTH, True):

            def bluetooth_configured() -> bool:
                return self.config_entry.data.get(
                    CONF_MAC, ""
                ) and self.config_entry.data.get(CONF_NAME, "")

            if not bluetooth_configured():
                machine = self.config_entry.data[CONF_MACHINE]
                for discovery_info in async_discovered_service_info(self.hass):
                    if (
                        (name := discovery_info.name)
                        and name.startswith(NAME_PREFIXES)
                        and name.split("_")[1] == machine
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
                # config entry contains BT config
                _LOGGER.debug("Initializing with known Bluetooth device")
                await self.lm.init_bluetooth_with_known_device(
                    self.config_entry.data[CONF_USERNAME],
                    self.config_entry.data.get(CONF_MAC, ""),
                    self.config_entry.data.get(CONF_NAME, ""),
                )
                self._use_bluetooth = True

        self.lm.initialized = True

    async def _async_handle_request[**_P](
        self,
        func: Callable[_P, Coroutine[None, None, None]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        """Handle a request to the API."""
        try:
            await func(*args, **kwargs)
        except AuthFail as ex:
            msg = "Authentication failed."
            _LOGGER.debug(msg, exc_info=True)
            raise ConfigEntryAuthFailed(msg) from ex
        except RequestNotSuccessful as ex:
            _LOGGER.debug(ex, exc_info=True)
            raise UpdateFailed(f"Querying API failed. Error: {ex}") from ex

    def async_get_ble_device(self) -> BLEDevice | None:
        """Get a Bleak Client for the machine."""
        # according to HA best practices, we should not reuse the same client
        # get a new BLE device from hass and init a new Bleak Client with it
        if not self._use_bluetooth:
            return None

        return async_ble_device_from_address(
            self.hass,
            self.lm.lm_bluetooth.address,
        )
