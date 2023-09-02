"""Represent the Netgear router and its devices."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from datetime import timedelta
import logging
from typing import Any

from pynetgear import Netgear

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_NAME,
    DOMAIN,
    MODE_ROUTER,
    MODELS_V2,
)
from .errors import CannotLoginException


class NetgearDeviceEntity(CoordinatorEntity):
    """Base class for a device connected to a Netgear router."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, router: NetgearRouter, device: dict
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator)
        self._router = router
        self._device = device
        self._mac = device["mac"]
        self._device_name = self._attr_name
        self._active = device["active"]
        self._attr_unique_id = self._mac
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac)},
            default_name=self._device_name,
            default_model=self._device["device_model"],
            via_device=(DOMAIN, self._router.unique_id),
        )

    def get_device_name(self):
        """Return the name of the given device or the MAC if we don't know."""
        name = self._device["name"]
        if not name or name == "--":
            name = self._mac

        return name

    @abstractmethod
    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_update_device()
        super()._handle_coordinator_update()


class NetgearRouterCoordinatorEntity(CoordinatorEntity):
    """Base class for a Netgear router entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, router: NetgearRouter
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator)
        self._router = router
        self._attr_unique_id = router.serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._router.unique_id)},
        )


    @abstractmethod
    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_update_device()
        super()._handle_coordinator_update()


class NetgearRouterEntity(Entity):
    """Base class for a Netgear router entity without coordinator."""

    def __init__(self, router: NetgearRouter) -> None:
        """Initialize a Netgear device."""
        self._router = router
        self._attr_unique_id = router.serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._router.unique_id)},
        )
