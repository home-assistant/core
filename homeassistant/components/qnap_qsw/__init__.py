"""The QNAP QSW integration."""
from __future__ import annotations

from typing import Any

from aioqsw.const import (
    QSD_FIRMWARE,
    QSD_FIRMWARE_INFO,
    QSD_MAC,
    QSD_PRODUCT,
    QSD_SYSTEM_BOARD,
)
from aioqsw.localapi import ConnectionOptions, QnapQswApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import QswUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


class QswEntity(CoordinatorEntity[QswUpdateCoordinator]):
    """Define an QNAP QSW entity."""

    def __init__(
        self,
        coordinator: QswUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            configuration_url=entry.data[CONF_URL],
            connections={
                (
                    CONNECTION_NETWORK_MAC,
                    self.get_device_value(QSD_SYSTEM_BOARD, QSD_MAC),
                )
            },
            manufacturer=MANUFACTURER,
            model=self.get_device_value(QSD_SYSTEM_BOARD, QSD_PRODUCT),
            name=self.get_device_value(QSD_SYSTEM_BOARD, QSD_PRODUCT),
            sw_version=self.get_device_value(QSD_FIRMWARE_INFO, QSD_FIRMWARE),
        )

    def get_device_value(self, key: str, subkey: str) -> Any:
        """Return device value by key."""
        value = None
        if key in self.coordinator.data:
            data = self.coordinator.data[key]
            if subkey in data:
                value = data[subkey]
        return value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up QNAP QSW from a config entry."""
    options = ConnectionOptions(
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    qsw = QnapQswApi(aiohttp_client.async_get_clientsession(hass), options)

    coordinator = QswUpdateCoordinator(hass, qsw)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
