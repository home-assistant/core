"""La Marzocco Cloud API client."""
from collections.abc import Mapping
import logging
from typing import Any

from lmcloud import LMCloud  # type: ignore[import]

from homeassistant.components import bluetooth
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_USERNAME
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
        await self._init_cloud_api(self._entry_data)
        _LOGGER.debug("Model name: %s", self.model_name)

        username = self._entry_data.get(CONF_USERNAME)
        mac_address = self._entry_data.get(CONF_MAC)
        name = self._entry_data.get(CONF_NAME)

        if mac_address is not None and name is not None:
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

        ip = self._entry_data.get(CONF_HOST)
        if ip is not None:
            _LOGGER.debug("Initializing local API")
            await self._init_local_api(
                ip=self._entry_data.get(CONF_HOST), port=DEFAULT_PORT_LOCAL
            )

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
        self, key: str, seconds_on: float, seconds_off: float
    ) -> None:
        """Set the prebrew times of the machine."""
        await self.configure_prebrew(
            prebrewOnTime=seconds_on * 1000, prebrewOffTime=seconds_off * 1000, key=key
        )

    async def set_preinfusion_time(self, key: str, seconds: float) -> None:
        """Set the preinfusion time of the machine."""
        await self.configure_prebrew(
            prebrewOnTime=0, prebrewOffTime=seconds * 1000, key=key
        )

    async def set_coffee_temp(self, temperature: float) -> None:
        """Set the coffee temperature of the machine."""
        await self.get_hass_bt_client()
        await super().set_coffee_temp(temperature)

    async def set_steam_temp(self, temperature: float) -> None:
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

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._lm_bluetooth.address, connectable=True
        )

        if ble_device is None:
            if not self._bt_disconnected:
                _LOGGER.warning(
                    "Machine not found in Bluetooth scan, not sending commands through bluetooth"
                )
                self._bt_disconnected = True
        elif self._bt_disconnected:
            _LOGGER.warning(
                "Machine available again for Bluetooth, sending commands through bluetooth"
            )
            self._bt_disconnected = False

        await self._lm_bluetooth.new_bleak_client_from_ble_device(ble_device)
