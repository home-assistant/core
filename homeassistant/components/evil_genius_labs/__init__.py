"""The Evil Genius Labs integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import cast

from aiohttp import ContentTypeError
import pyevilgenius

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

PLATFORMS = [Platform.LIGHT]

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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class EvilGeniusUpdateCoordinator(DataUpdateCoordinator[dict]):  # pylint: disable=hass-enforce-coordinator-module
    """Update coordinator for Evil Genius data."""

    info: dict

    product: dict | None

    def __init__(
        self, hass: HomeAssistant, name: str, client: pyevilgenius.EvilGeniusDevice
    ) -> None:
        """Initialize the data update coordinator."""
        self.client = client
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=name,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    @property
    def device_name(self) -> str:
        """Return the device name."""
        return cast(str, self.data["name"]["value"])

    @property
    def product_name(self) -> str | None:
        """Return the product name."""
        if self.product is None:
            return None

        return cast(str, self.product["productName"])

    async def _async_update_data(self) -> dict:
        """Update Evil Genius data."""
        if not hasattr(self, "info"):
            async with asyncio.timeout(5):
                self.info = await self.client.get_info()

        if not hasattr(self, "product"):
            async with asyncio.timeout(5):
                try:
                    self.product = await self.client.get_product()
                except ContentTypeError:
                    # Older versions of the API don't support this
                    self.product = None

        async with asyncio.timeout(5):
            return cast(dict, await self.client.get_all())


class EvilGeniusEntity(CoordinatorEntity[EvilGeniusUpdateCoordinator]):
    """Base entity for Evil Genius."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        info = self.coordinator.info
        return DeviceInfo(
            identifiers={(DOMAIN, info["wiFiChipId"])},
            connections={(dr.CONNECTION_NETWORK_MAC, info["macAddress"])},
            name=self.coordinator.device_name,
            model=self.coordinator.product_name,
            manufacturer="Evil Genius Labs",
            sw_version=info["coreVersion"].replace("_", "."),
            configuration_url=self.coordinator.client.url,
        )
