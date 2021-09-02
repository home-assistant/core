"""Component to control TOLO Sauna/Steam Bath."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, cast

from tololib import ToloClient
from tololib.message_info import SettingsInfo, StatusInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from ...helpers.entity import DeviceInfo
from .const import DEFAULT_NAME, DEFAULT_RETRY_COUNT, DEFAULT_RETRY_TIMEOUT, DOMAIN

PLATFORMS = ["climate"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tolosauna from a config entry."""
    client = ToloClient(entry.data[CONF_HOST])
    coordinator = ToloSaunaUpdateCoordinator(hass, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"client": client, "coordinator": coordinator}
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class ToloSaunaUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for TOLO Sauna."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize ToloSaunaUpdateCoordinator."""
        self._config_entry = entry
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DEFAULT_NAME} Data Update Coordinator",
            update_method=self._update_data,
            update_interval=timedelta(seconds=3),
        )

    async def _update_data(self) -> dict[str, Any]:
        client = ToloClient(self._config_entry.data[CONF_HOST])
        status = client.get_status_info(
            resend_timeout=DEFAULT_RETRY_TIMEOUT, retries=DEFAULT_RETRY_COUNT
        )
        settings = client.get_settings_info(
            resend_timeout=DEFAULT_RETRY_TIMEOUT, retries=DEFAULT_RETRY_COUNT
        )
        return {"status": status, "settings": settings}


class ToloSaunaCoordinatorEntity(CoordinatorEntity):
    """CoordinatorEntity for TOLO Sauna."""

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize ToloSaunaCoordinatorEntity."""
        self._config_entry = entry
        super().__init__(coordinator)

    @property
    def status(self) -> StatusInfo:
        """Return TOLO Sauna status info."""
        return cast(StatusInfo, self.coordinator.data["status"])

    @property
    def settings(self) -> SettingsInfo:
        """Return TOLO Sauna settings info."""
        return cast(SettingsInfo, self.coordinator.data["settings"])

    @property
    def client(self) -> ToloClient:
        """Return ToloClient instance."""
        return cast(
            ToloClient, self.hass.data[DOMAIN][self._config_entry.entry_id]["client"]
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            name="TOLO Sauna",
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            manufacturer="SteamTec",
            model=str(self.status.model.name).capitalize(),
        )
