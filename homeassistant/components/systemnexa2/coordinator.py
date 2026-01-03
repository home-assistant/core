"""Data coordinator for System Nexa 2 integration."""

import logging

from sn2 import (
    ConnectionStatus,
    Device,
    DeviceInitializationError,
    InformationData,
    OnOffSetting,
    SettingsUpdate,
    StateChange,
)
from sn2.device import Setting, UpdateEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type SystemNexa2ConfigEntry = ConfigEntry[SystemNexa2DataUpdateCoordinator]


class SystemNexa2Data:
    """Data container for System Nexa 2 device information."""

    __slots__ = (
        "available",
        "info_data",
        "on_off_settings",
        "state",
        "unique_id",
    )

    info_data: InformationData
    unique_id: str
    on_off_settings: dict[str, OnOffSetting]
    state: float | None
    available: bool

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
        """Initialize my coordinator."""
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
        self._unavailable_logged = False
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
                "Failed to initialize device with IP/Hostname '%s', please verify that the device is powered on and reachable on port 3000",
                self.config_entry.data[CONF_HOST],
            )
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="failed_to_initiate_connection",
                translation_placeholders={CONF_HOST: self.config_entry.data[CONF_HOST]},
            ) from e

        self.data.available = False
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
        data.available = (
            _is_connected
            and data.on_off_settings is not None
            and self._state_received_once
            and data.state is not None
        )

        if not data.available and not self._unavailable_logged:
            _LOGGER.info(
                "Device %s is unavailable",
                self.config_entry.data[CONF_HOST],
            )
            self._unavailable_logged = True
        elif data.available and self._unavailable_logged:
            _LOGGER.info(
                "Device %s is back online",
                self.config_entry.data[CONF_HOST],
            )
            self._unavailable_logged = False

        self.async_set_updated_data(data)
