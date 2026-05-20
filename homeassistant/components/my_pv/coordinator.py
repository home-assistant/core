"""The my-PV integration for Home Assistant."""

from datetime import timedelta
import functools
import logging
from typing import Any

from my_pv import MyPVDevice
from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _my_pv_connecton(func):
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self._device.connected and not await self._device.connect():
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )

        try:
            return await func(self, *args, **kwargs)
        except MyPVAuthenticationError as exc:
            raise ConfigEntryAuthFailed from exc
        except MyPVConnectionError as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_unavailable",
                translation_placeholders={"uri": self._device.uri},
            ) from exc

    return wrapper


class MyPVCoordinator(DataUpdateCoordinator[None]):
    """my-PV Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: MyPVDevice,
    ) -> None:
        """Initialize my-PV Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=__name__,
            config_entry=config_entry,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=5),
            always_update=True,
        )

        self._device = device

        identifiers = {
            (DOMAIN, device.serial_number),
        }
        connections = set()

        if device.mac_address:
            connections.add((CONNECTION_NETWORK_MAC, device.mac_address))

        name = f"my-PV {device.model}"

        self._device_info = DeviceInfo(
            configuration_url=device.setup_uri,
            connections=connections,
            identifiers=identifiers,
            manufacturer="my-PV",
            model=device.model,
            name=name,
            serial_number=device.serial_number,
            sw_version=device.firmware_version,
            hw_version=device.hardware_version,
        )

    @property
    def device(self) -> MyPVDevice:
        """The my-PV device."""
        return self._device

    @property
    def device_info(self) -> DeviceInfo:
        """The Device info."""
        return self._device_info

    @property
    def connected(self) -> bool:
        """If the device is connected or not."""
        return self._device.connected

    def get_setup_configuration(self, key: str) -> dict[str, Any] | None:
        """Get setup configuration for given key."""
        return self._device.get_setup_configuration(key)

    def supports_data(self, key: str) -> bool:
        """Test if data for the given key is supported."""
        return self._device.supports_data(key)

    def get_data_configuration(self, key: str) -> dict[str, Any] | None:
        """Get data configuration for given key."""
        return self._device.get_data_configuration(key)

    def supports_command(self, command: str) -> bool:
        """Test if the given command is supported."""
        return self._device.supports_command(command)

    async def async_disconnect(self) -> bool:
        """Disconnect from my-PV.

        To be called when coordinator is unloaded, e.g. when device is removed or HA is shutdown.
        """
        return await self._device.disconnect()

    @_my_pv_connecton
    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self._device.fetch_data()

    @_my_pv_connecton
    async def set_target_temperature(self, temperature: float) -> bool:
        """Set setup value for the given key."""
        result = await self._device.set_target_temperature(temperature)
        self.async_update_listeners()
        return result

    def get_data_value(self, key: str) -> bool | float | int | str | None:
        """Get the data value for the given key."""
        return self._device.get_data_value(key)

    @_my_pv_connecton
    async def turn_on(self):
        """Turn on the device."""
        result = await self._device.turn_on()
        self.async_update_listeners()
        return result

    @_my_pv_connecton
    async def turn_off(self):
        """Turn off the device."""
        result = await self._device.turn_off()
        self.async_update_listeners()
        return result


type MyPVConfigEntry = ConfigEntry[MyPVCoordinator]
