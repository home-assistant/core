"""La Marzocco Cloud API client."""
from collections.abc import Mapping
import logging
from typing import Any

from lmcloud import LMCloud
from lmcloud.exceptions import BluetoothConnectionFailed

from homeassistant.components import bluetooth
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_PORT_LOCAL,
    MACHINE_NAME,
    MODEL_GS3_AV,
    MODEL_GS3_MP,
    MODEL_LM,
    MODEL_LMU,
    SERIAL_NUMBER,
)

_LOGGER = logging.getLogger(__name__)

MODELS = [MODEL_GS3_AV, MODEL_GS3_MP, MODEL_LM, MODEL_LMU]


class LaMarzoccoClient(LMCloud):
    """Keep data for La Marzocco entities."""

    def __init__(self, hass: HomeAssistant, entry_data: Mapping[str, Any]) -> None:
        """Initialise the LaMarzocco entity data."""
        super().__init__()

        self._device_version: str | None = None
        self._entry_data = entry_data
        self.hass = hass
        self._brew_active = False
        self._bt_disconnected = False

    @property
    def model_name(self) -> str:
        """Return model name."""
        if super().model_name not in MODELS:
            _LOGGER.exception(
                "Unsupported model, falling back to all entities and services %s",
                super().model_name,
            )
        return super().model_name if super().model_name in MODELS else MODEL_GS3_AV

    @property
    def true_model_name(self) -> str:
        """Return the model name from the cloud, even if it's not one we know about. Used for display only."""
        if self.model_name == MODEL_LMU:
            return f"Linea {MODEL_LMU}"
        if self.model_name in MODELS:
            return self.model_name
        return f"Unsupported Model ({self.model_name})"

    @property
    def machine_name(self) -> str:
        """Return the name of the machine."""
        return self.machine_info[MACHINE_NAME]

    @property
    def serial_number(self) -> str:
        """Return serial number."""
        return self.machine_info[SERIAL_NUMBER]

    async def connect(self) -> None:
        """Connect to the machine."""
        _LOGGER.debug("Initializing Cloud API")
        credentials = {
            CONF_USERNAME: self._entry_data.get(CONF_USERNAME, ""),
            CONF_PASSWORD: self._entry_data.get(CONF_PASSWORD, ""),
            CONF_CLIENT_SECRET: self._entry_data.get(CONF_CLIENT_SECRET, ""),
            CONF_CLIENT_ID: self._entry_data.get(CONF_CLIENT_ID, ""),
        }
        await self._init_cloud_api(credentials=credentials)
        _LOGGER.debug("Model name: %s", self.model_name)

        username: str = self._entry_data.get(CONF_USERNAME, "")
        mac_address: str = self._entry_data.get(CONF_MAC, "")
        name: str = self._entry_data.get(CONF_NAME, "")

        if mac_address and name:
            # coming from discovery
            _LOGGER.debug("Initializing with known Bluetooth device")
            await self._init_bluetooth_with_known_device(username, mac_address, name)
        else:
            # check if there are any bluetooth adapters to use
            count = bluetooth.async_scanner_count(self.hass, connectable=True)
            if count > 0:
                _LOGGER.debug("Found Bluetooth adapters, initializing with Bluetooth")
                bt_scanner = bluetooth.async_get_scanner(self.hass)

                await self._init_bluetooth(
                    username=username, init_client=False, bluetooth_scanner=bt_scanner
                )

        if self._lm_bluetooth:
            _LOGGER.debug("Connecting to machine with Bluetooth")
            await self.get_hass_bt_client()

        host: str = self._entry_data.get(CONF_HOST, "")
        if host:
            _LOGGER.debug("Initializing local API")
            await self._init_local_api(host=host, port=DEFAULT_PORT_LOCAL)

    async def try_connect(self, data: dict[str, Any]) -> dict[str, Any]:
        """Try to connect to the machine, used for validation."""
        self.client = await self._connect(data)
        machine_info = await self._get_machine_info()
        return machine_info

    async def set_power(self, enabled: bool) -> None:
        """Set the power state of the machine."""
        await self.get_hass_bt_client()
        await super().set_power(enabled)

    async def set_steam_boiler_enable(self, enable: bool) -> None:
        """Set the steam boiler state of the machine."""
        await self.get_hass_bt_client()
        await self.set_steam(enable)

    async def set_auto_on_off_global(self, enable: bool) -> None:
        """Set the auto on/off state of the machine."""
        await self.configure_schedule(enable, self.schedule)

    async def set_prebrew_times(
        self, key: int, seconds_on: float, seconds_off: float
    ) -> None:
        """Set the prebrew times of the machine."""
        await self.configure_prebrew(
            on_time=seconds_on * 1000, off_time=seconds_off * 1000, key=key
        )

    async def set_preinfusion_time(self, key: int, seconds: float) -> None:
        """Set the preinfusion time of the machine."""
        await self.configure_prebrew(on_time=0, off_time=seconds * 1000, key=key)

    async def set_coffee_temp(self, temperature: float) -> None:
        """Set the coffee temperature of the machine."""
        await self.get_hass_bt_client()
        await super().set_coffee_temp(temperature)

    async def set_steam_temp(self, temperature: int) -> None:
        """Set the steam temperature of the machine."""
        possible_temps = [126, 128, 131]
        min(possible_temps, key=lambda x: abs(x - temperature))
        await self.get_hass_bt_client()
        await super().set_steam_temp(temperature)

    async def get_hass_bt_client(self) -> None:
        """Get a Bleak Client for the machine."""
        # according to HA best practices, we should not reuse the same client
        # get a new BLE device from hass and init a new Bleak Client with it
        if self._lm_bluetooth is None:
            return

        assert self._lm_bluetooth.address
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._lm_bluetooth.address, connectable=True
        )

        if ble_device is None:
            if not self._bt_disconnected:
                _LOGGER.warning(
                    "Machine not found in Bluetooth scan, not sending commands through bluetooth"
                )
                self._bt_disconnected = True
            return

        if self._bt_disconnected:
            _LOGGER.warning(
                "Machine available again for Bluetooth, sending commands through bluetooth"
            )
            self._bt_disconnected = False
        try:
            await self._lm_bluetooth.new_bleak_client_from_ble_device(ble_device)
        except BluetoothConnectionFailed as ex:
            _LOGGER.warning(ex)
