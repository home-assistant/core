"""Data coordinator for System Nexa 2 integration."""

from collections.abc import Awaitable
import logging

import aiohttp
from sn2 import (
    ConnectionStatus,
    Device,
    DeviceInitializationError,
    InformationData,
    NotConnectedError,
    OnOffSetting,
    SettingsUpdate,
    StateChange,
)
from sn2.device import Setting, UpdateEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type SystemNexa2ConfigEntry = ConfigEntry[SystemNexa2DataUpdateCoordinator]


class InsufficientDeviceInformation(Exception):
    """Exception raised when device does not provide sufficient information."""


class SystemNexa2Data:
    """Data container for System Nexa 2 device information."""

    __slots__ = (
        "info_data",
        "on_off_settings",
        "state",
        "unique_id",
    )

    info_data: InformationData
    unique_id: str
    on_off_settings: dict[str, OnOffSetting]
    state: float | None

    def __init__(self) -> None:
        """Initialize the data container."""
        self.state = None
        self.on_off_settings = {}

    def update_settings(self, settings: list[Setting]) -> None:
        """Update the on/off settings from a list of settings."""
        self.on_off_settings = {
            setting.name: setting
            for setting in settings
            if isinstance(setting, OnOffSetting)
        }


class SystemNexa2DataUpdateCoordinator(DataUpdateCoordinator[SystemNexa2Data]):
    """Data update coordinator for System Nexa 2 devices."""

    config_entry: SystemNexa2ConfigEntry
    info_data: InformationData
    device: Device

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SystemNexa2ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=None,
            update_method=None,
            always_update=False,
        )
        self._state_received_once = False
        self.data = SystemNexa2Data()

    async def async_setup(self) -> None:
        """Set up the coordinator and initialize the device connection."""
        try:
            self.device = await Device.initiate_device(
                host=self.config_entry.data[CONF_HOST],
                on_update=self._async_handle_update,
                session=async_get_clientsession(self.hass),
            )

        except DeviceInitializationError as e:
            _LOGGER.error(
                "Failed to initialize device with IP/Hostname %s, please verify that the device is powered on and reachable on port 3000",
                self.config_entry.data[CONF_HOST],
            )
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="failed_to_initiate_connection",
                translation_placeholders={CONF_HOST: self.config_entry.data[CONF_HOST]},
            ) from e

        self.data.unique_id = self.device.info_data.unique_id
        self.data.info_data = self.device.info_data
        self.data.update_settings(self.device.settings)
        await self.device.connect()

    async def _async_handle_update(self, event: UpdateEvent) -> None:
        data = self.data or SystemNexa2Data()
        _is_connected = True
        match event:
            case ConnectionStatus(connected):
                _is_connected = connected
            case StateChange(state):
                data.state = state
                self._state_received_once = True
            case SettingsUpdate(settings):
                data.update_settings(settings)

        if not _is_connected:
            self.async_set_update_error(ConnectionError("No connection to device"))
        elif (
            data.on_off_settings is not None
            and self._state_received_once
            and data.state is not None
        ):
            self.async_set_updated_data(data)

    async def _async_sn2_call_with_error_handling(self, coro: Awaitable[None]) -> None:
        """Execute a coroutine with error handling."""
        try:
            await coro
        except (TimeoutError, NotConnectedError, aiohttp.ClientError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_communication_error",
            ) from err

    async def async_turn_on(self) -> None:
        """Turn on the device."""
        await self._async_sn2_call_with_error_handling(self.device.turn_on())

    async def async_turn_off(self) -> None:
        """Turn off the device."""
        await self._async_sn2_call_with_error_handling(self.device.turn_off())

    async def async_toggle(self) -> None:
        """Toggle the device."""
        await self._async_sn2_call_with_error_handling(self.device.toggle())

    async def async_setting_enable(self, setting: OnOffSetting) -> None:
        """Enable a device setting."""
        await self._async_sn2_call_with_error_handling(setting.enable(self.device))

    async def async_setting_disable(self, setting: OnOffSetting) -> None:
        """Disable a device setting."""
        await self._async_sn2_call_with_error_handling(setting.disable(self.device))
