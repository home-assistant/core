
import logging

from homeassistant.components import bluetooth
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_USERNAME
from lmcloud import LMCloud

from .const import (
    DEFAULT_PORT_CLOUD,
    MODEL_GS3_AV,
    MODEL_GS3_MP,
    MODEL_LM,
    MODEL_LMU,
)

_LOGGER = logging.getLogger(__name__)

MODELS = [MODEL_GS3_AV, MODEL_GS3_MP, MODEL_LM, MODEL_LMU]


class LaMarzoccoClient(LMCloud):
    """Keep data for La Marzocco entities."""

    def __init__(self, hass, hass_config):
        """Initialise the LaMarzocco entity data."""
        super().__init__()

        self._device_version = None
        self._hass_config = hass_config
        self.hass = hass
        self._brew_active = False
        self._bt_disconnected = False

    @property
    def model_name(self) -> str:
        """Return model name."""
        if super().model_name not in MODELS:
            _LOGGER.error(
                f"Unsupported model, falling back to all entities and services: {super().model_name}"
            )
        return super().model_name if super().model_name in MODELS else MODEL_GS3_AV

    @property
    def true_model_name(self) -> str:
        """Return the model name from the cloud, even if it's not one we know about.  Used for display only."""
        return self.model_name if self.model_name in MODELS else self.model_name + " (Unknown)"

    @property
    def machine_name(self) -> str:
        """Return the name of the machine."""
        return self.machine_info["machine_name"]

    @property
    def serial_number(self) -> str:
        """Return serial number."""
        return self.machine_info["serial_number"]

    '''
    Initialization
    '''

    async def hass_init(self) -> None:

        _LOGGER.debug("Initializing Cloud API.")
        await self._init_cloud_api(self._hass_config)
        _LOGGER.debug(f"Model name: {self.model_name}")

        username = self._hass_config.get(CONF_USERNAME)
        mac_address = self._hass_config.get(CONF_MAC)
        name = self._hass_config.get(CONF_NAME)

        if mac_address is not None and name is not None:
            # coming from discovery
            _LOGGER.debug("Initializing with known BT device.")
            await self._init_bluetooth_with_known_device(username, mac_address, name)
        else:
            # check if there are any bluetooth adapters to use
            count = bluetooth.async_scanner_count(self.hass, connectable=True)
            if count > 0:
                _LOGGER.debug("Found bluetooth adapters, initializing with bluetooth.")
                bt_scanner = bluetooth.async_get_scanner(self.hass)

                await self._init_bluetooth(username=username,
                                           init_client=False,
                                           bluetooth_scanner=bt_scanner)

        if self._lm_bluetooth:
            _LOGGER.debug("Connecting to machine with Bluetooth.")
            await self.get_hass_bt_client()

        ip = self._hass_config.get(CONF_HOST)
        if ip is not None:
            _LOGGER.debug("Initializing local API.")
            await self._init_local_api(
                ip=self._hass_config.get(CONF_HOST),
                port=DEFAULT_PORT_CLOUD
            )

    '''
    interface methods
    '''

    async def set_power(self, power_on) -> None:
        await self.get_hass_bt_client()
        await super().set_power(power_on)

    async def set_steam_boiler_enable(self, enable) -> None:
        await self.get_hass_bt_client()
        await self.set_steam(enable)

    async def set_auto_on_off_global(self, enable) -> None:
        await self.configure_schedule(enable, self.schedule)

    async def set_prebrew_times(self, key, seconds_on, seconds_off) -> None:
        await self.configure_prebrew(
            prebrewOnTime=seconds_on * 1000,
            prebrewOffTime=seconds_off * 1000,
            key=key
        )

    async def set_preinfusion_time(self, key, seconds) -> None:
        await self.configure_prebrew(
            prebrewOnTime=0,
            prebrewOffTime=seconds * 1000,
            key=key
        )

    async def set_coffee_temp(self, temp) -> None:
        await self.get_hass_bt_client()
        await super().set_coffee_temp(temp)

    async def set_steam_temp(self, temp) -> None:
        possible_temps = [126, 128, 131]
        temp = min(possible_temps, key=lambda x: abs(x - temp))
        await self.get_hass_bt_client()
        await super().set_steam_temp(temp)

    async def get_hass_bt_client(self) -> None:
        # according to HA best practices, we should not reuse the same client
        # get a new BLE device from hass and init a new Bleak Client with it
        if self._lm_bluetooth is None:
            return

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass,
            self._lm_bluetooth._address,
            connectable=True
        )

        if ble_device is None:
            if not self._bt_disconnected:
                _LOGGER.warn("Machine not found in Bluetooth scan, not sending commands through bluetooth.")
                self._bt_disconnected = True
        else:
            if self._bt_disconnected:
                _LOGGER.warn("Machine available again for Bluetooth, sending commands through bluetooth.")
                self._bt_disconnected = False

        await self._lm_bluetooth.new_bleak_client_from_ble_device(ble_device)
