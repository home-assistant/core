"""The my-PV integration for Home Assistant."""

from collections.abc import ItemsView
from datetime import timedelta
import logging
from typing import Any

from my_pv import MyPVDevice
from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MyPVCoordinator(DataUpdateCoordinator):
    """my-PV Data Update Coordinator."""

    _device: MyPVDevice
    _device_info: DeviceInfo

    _data_configurations: ItemsView[str, Any] | None = None
    _setup_configurations: ItemsView[str, Any] | None = None
    _command_configurations: ItemsView[str, Any] | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: MyPVDevice,
        update_interval: timedelta,
    ) -> None:
        """Initialize my-PV Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=__name__,
            config_entry=config_entry,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=update_interval,
            always_update=True,
        )

        self._device = device

        identifiers = {
            (DOMAIN, device.serial_number),
        }
        connections = set()

        if device.mac_address is not None:
            mac_address = format_mac(device.mac_address)
            identifiers.add((DOMAIN, mac_address))
            connections.add((CONNECTION_NETWORK_MAC, mac_address))

        model = device.model
        if device.hardware_version:
            model = f"{device.model} {device.hardware_version}"

        name = f"my-PV {device.model}"

        self._device_info = DeviceInfo(
            configuration_url=device.setup_uri,
            connections=connections,
            identifiers=identifiers,
            manufacturer="my-PV",
            model=model,
            name=name,
            serial_number=device.serial_number,
            sw_version=device.firmware_version,
            translation_key="my_pv",
            translation_placeholders={
                "device_name": name,
            },
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

    @property
    def setup_configurations(self) -> ItemsView[str, Any]:
        """Get the configurations for the available setup parameters."""
        if not self._setup_configurations:
            self._setup_configurations = self._device.get_setup_configurations().items()
        return self._setup_configurations

    def get_setup_configuration(self, key: str) -> dict | None:
        """Get setup configuration for given key."""
        return self._device.get_setup_configuration(key)

    def supports_data(self, key: str) -> bool:
        """Test if data for the given key is supported."""
        return self._device.supports_data(key)

    @property
    def data_configurations(self) -> ItemsView[str, Any]:
        """Get the configurations for the available data."""
        if not self._data_configurations:
            self._data_configurations = self._device.get_data_configurations().items()
        return self._data_configurations

    def get_data_configuration(self, key: str) -> dict | None:
        """Get data configuration for given key."""
        return self._device.get_data_configuration(key)

    def supports_command(self, command: str) -> bool:
        """Test if the given command is supported."""
        return self._device.supports_command(command)

    @property
    def command_configurations(self) -> ItemsView[str, Any]:
        """Get the configurations for the available commands."""
        if not self._command_configurations:
            self._command_configurations = (
                self._device.get_command_configurations().items()
            )
        return self._command_configurations

    async def async_disconnect(self) -> bool:
        """Disconnect from my-PV.

        To be called when coordinator is unloaded, e.g. when device is removed or HA is shutdown.
        """
        return await self._device.disconnect()

    async def reload_config(self):
        """Reload the device configuration."""
        await self.async_disconnect()
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    async def _async_setup(self):
        """Set up the coordinator."""

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        if not self._device.connected and not await self._device.connect():
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"uri": self._device.uri},
            )

        try:
            await self._device.fetch_data()
        except MyPVAuthenticationError as exc:
            raise ConfigEntryAuthFailed from exc
        except MyPVConnectionError as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_unavailable",
                translation_placeholders={"uri": self._device.uri},
            ) from exc

        return {}

    def get_setup_value(self, key: str) -> bool | float | int | str | None:
        """Get the setup value for the given key."""
        return self._device.get_setup_value(key)

    async def set_setup_value(self, key: str, value: bool | float | str) -> bool:
        """Set setup value for the given key."""
        result = await self._device.set_setup_value(key, value)
        self.async_update_listeners()
        return result

    def get_data_value(self, key: str) -> bool | float | int | str | None:
        """Get the data value for the given key."""
        return self._device.get_data_value(key)

    async def send_command(self, key, value: bool | float | str | None = None):
        """Send command."""
        result = await self._device.send_command(key, value)
        self.async_update_listeners()
        return result
