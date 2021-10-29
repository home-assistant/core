"""The Evil Genius Labs integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from async_timeout import timeout
import pyevilgenius

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    update_coordinator,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

PLATFORMS = ["light"]

UPDATE_INTERVAL = 10


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Evil Genius Labs from a config entry."""
    coordinator = EvilGeniusUpdateCoordinator(
        hass,
        entry.title,
        pyevilgenius.EvilGeniusDevice(
            entry.data["host"], aiohttp_client.async_get_clientsession(hass)
        ),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class EvilGeniusUpdateCoordinator(update_coordinator.DataUpdateCoordinator):
    """Update coordinator for Evil Genius data."""

    info: dict

    def __init__(
        self, hass: HomeAssistant, name: str, client: pyevilgenius.EvilGeniusDevice
    ):
        """Initialize the data update coordinator."""
        self.client = client
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=name,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    @property
    def device_name(self):
        """Return the device name."""
        return self.data["name"]["value"]

    async def _async_update_data(self):
        """Update Evil Genius data."""
        if not hasattr(self, "info"):
            async with timeout(5):
                self.info = await self.client.get_info()

        async with timeout(5):
            return await self.client.get_data()


class EvilGeniusEntity(update_coordinator.CoordinatorEntity):
    """Base entity for Evil Genius."""

    coordinator: EvilGeniusUpdateCoordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        info = self.coordinator.info
        data = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, info["wiFiChipId"])},
            connections={(dr.CONNECTION_NETWORK_MAC, info["macAddress"])},
            name=data["name"]["value"],
            manufacturer="Evil Genius Labs",
            sw_version=info["coreVersion"].replace("_", "."),
            configuration_url=self.coordinator.client.url,
        )
