"""The PrusaLink integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
import logging
from time import monotonic
from typing import Generic, TypeVar

import async_timeout
from pyprusalink import InvalidAuth, JobInfo, PrinterInfo, PrusaLink, PrusaLinkError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.CAMERA, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PrusaLink from a config entry."""
    api = PrusaLink(
        async_get_clientsession(hass),
        entry.data["host"],
        entry.data["api_key"],
    )

    coordinators = {
        "printer": PrinterUpdateCoordinator(hass, api),
        "job": JobUpdateCoordinator(hass, api),
    }
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


T = TypeVar("T", PrinterInfo, JobInfo)


class PrusaLinkUpdateCoordinator(DataUpdateCoordinator, Generic[T], ABC):
    """Update coordinator for the printer."""

    config_entry: ConfigEntry
    expect_change_until = 0.0

    def __init__(self, hass: HomeAssistant, api: PrusaLink) -> None:
        """Initialize the update coordinator."""
        self.api = api

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=self._get_update_interval(None)
        )

    async def _async_update_data(self) -> T:
        """Update the data."""
        try:
            async with async_timeout.timeout(5):
                data = await self._fetch_data()
        except InvalidAuth:
            raise UpdateFailed("Invalid authentication") from None
        except PrusaLinkError as err:
            raise UpdateFailed(str(err)) from err

        self.update_interval = self._get_update_interval(data)
        return data

    @abstractmethod
    async def _fetch_data(self) -> T:
        """Fetch the actual data."""
        raise NotImplementedError

    @callback
    def expect_change(self) -> None:
        """Expect a change."""
        self.expect_change_until = monotonic() + 30

    def _get_update_interval(self, data: T) -> timedelta:
        """Get new update interval."""
        if self.expect_change_until > monotonic():
            return timedelta(seconds=5)

        return timedelta(seconds=30)


class PrinterUpdateCoordinator(PrusaLinkUpdateCoordinator[PrinterInfo]):
    """Printer update coordinator."""

    async def _fetch_data(self) -> PrinterInfo:
        """Fetch the printer data."""
        return await self.api.get_printer()

    def _get_update_interval(self, data: T) -> timedelta:
        """Get new update interval."""
        if data and any(
            data["state"]["flags"][key] for key in ("pausing", "cancelling")
        ):
            return timedelta(seconds=5)

        return super()._get_update_interval(data)


class JobUpdateCoordinator(PrusaLinkUpdateCoordinator[JobInfo]):
    """Job update coordinator."""

    async def _fetch_data(self) -> JobInfo:
        """Fetch the printer data."""
        return await self.api.get_job()


class PrusaLinkEntity(CoordinatorEntity[PrusaLinkUpdateCoordinator]):
    """Defines a base PrusaLink entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this PrusaLink device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=self.coordinator.config_entry.title,
            manufacturer="Prusa",
            configuration_url=self.coordinator.api.host,
        )
