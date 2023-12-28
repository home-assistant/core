"""Component to control TOLO Sauna/Steam Bath."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import NamedTuple

from tololib import ToloClient
from tololib.errors import ResponseTimedOutError
from tololib.message_info import SettingsInfo, StatusInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DEFAULT_RETRY_COUNT, DEFAULT_RETRY_TIMEOUT, DOMAIN

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tolo from a config entry."""
    coordinator = ToloSaunaUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class ToloSaunaData(NamedTuple):
    """Compound class for reflecting full state (status and info) of a TOLO Sauna."""

    status: StatusInfo
    settings: SettingsInfo


class ToloSaunaUpdateCoordinator(DataUpdateCoordinator[ToloSaunaData]):
    """DataUpdateCoordinator for TOLO Sauna."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize ToloSaunaUpdateCoordinator."""
        self.client = ToloClient(entry.data[CONF_HOST])
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{entry.title} ({entry.data[CONF_HOST]}) Data Update Coordinator",
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> ToloSaunaData:
        return await self.hass.async_add_executor_job(self._get_tolo_sauna_data)

    def _get_tolo_sauna_data(self) -> ToloSaunaData:
        try:
            status = self.client.get_status_info(
                resend_timeout=DEFAULT_RETRY_TIMEOUT, retries=DEFAULT_RETRY_COUNT
            )
            settings = self.client.get_settings_info(
                resend_timeout=DEFAULT_RETRY_TIMEOUT, retries=DEFAULT_RETRY_COUNT
            )
        except ResponseTimedOutError as error:
            raise UpdateFailed("communication timeout") from error
        return ToloSaunaData(status, settings)


class ToloSaunaCoordinatorEntity(CoordinatorEntity[ToloSaunaUpdateCoordinator]):
    """CoordinatorEntity for TOLO Sauna."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize ToloSaunaCoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            name="TOLO Sauna",
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="SteamTec",
            model=self.coordinator.data.status.model.name.capitalize(),
        )
