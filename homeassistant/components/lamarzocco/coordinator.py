"""Coordinator for La Marzocco API."""
from datetime import timedelta
import logging

from bleak.backends.device import BLEDevice
from lmcloud import LMCloud as LaMarzoccoClient
from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_MACHINE, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to handle fetching data from the La Marzocco API centrally."""

    config_entry: ConfigEntry

    @property
    def lm(self) -> LaMarzoccoClient:
        """Return the LaMarzoccoClient instance."""
        return self._lm

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self._lm = LaMarzoccoClient(
            callback_websocket_notify=self.async_update_listeners,
        )
        self._use_bluetooth = False

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        _LOGGER.debug("Update coordinator: Updating data")
        try:
            if not self._lm.initialized:
                await self._async_init_client()
            await self._lm.update_local_machine_status(force_update=True)

        except AuthFail as ex:
            msg = "Authentication failed. \
                            Maybe one of your credential details was invalid or you changed your password."
            _LOGGER.debug(msg, exc_info=True)
            raise ConfigEntryAuthFailed(msg) from ex
        except RequestNotSuccessful as ex:
            _LOGGER.debug(ex, exc_info=True)
            raise UpdateFailed("Querying API failed. Error: %s" % ex) from ex

        _LOGGER.debug("Current status: %s", str(self._lm.current_status))

    async def _async_init_client(self) -> None:
        """Initialize the La Marzocco Client."""

        username = self.config_entry.data[CONF_USERNAME]
        # only set when discovered via Bluetooth
        mac_address: str = self.config_entry.data.get(CONF_MAC, "")
        name: str = self.config_entry.data.get(CONF_NAME, "")
        host: str = self.config_entry.data.get(CONF_HOST, "")

        # Initialize cloud API
        _LOGGER.debug("Initializing Cloud API")
        await self._lm.init_cloud_api(
            credentials=self.config_entry.data,
            machine_serial=self.config_entry.data[CONF_MACHINE],
        )
        _LOGGER.debug("Model name: %s", self._lm.model_name)

        # initialize Bluetooth
        if mac_address and name:
            # coming from discovery
            _LOGGER.debug("Initializing with known Bluetooth device")
            self._use_bluetooth = True
            await self._lm.init_bluetooth_with_known_device(username, mac_address, name)
        else:
            # check if there are any bluetooth adapters to use
            count = bluetooth.async_scanner_count(self.hass, connectable=True)
            if count > 0:
                _LOGGER.debug("Found Bluetooth adapters, initializing with Bluetooth")
                self._use_bluetooth = True
                bt_scanner = bluetooth.async_get_scanner(self.hass)

                await self._lm.init_bluetooth(
                    username=username,
                    init_client=False,
                    bluetooth_scanner=bt_scanner,
                )

                # update the config entry with the MAC address
                new_data = self.config_entry.data.copy()
                new_data[CONF_MAC] = self._lm.lm_bluetooth.address
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                )

        # initialize local API
        if host:
            _LOGGER.debug("Initializing local API")
            await self._lm.init_local_api(host)

            _LOGGER.debug("Init WebSocket in Background Task")

            self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self._lm.lm_local_api.websocket_connect(
                    callback=self._lm.on_websocket_message_received,
                    use_sigterm_handler=False,
                ),
                name="lm_websocket_task",
            )

        self._lm.initialized = True

    def async_get_ble_device(self) -> BLEDevice | None:
        """Get a Bleak Client for the machine."""
        # according to HA best practices, we should not reuse the same client
        # get a new BLE device from hass and init a new Bleak Client with it
        if not self._use_bluetooth:
            return None

        return bluetooth.async_ble_device_from_address(
            self.hass, self._lm.lm_bluetooth.address, connectable=True
        )
