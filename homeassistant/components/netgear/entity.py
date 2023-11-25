"""Represent the Netgear router and its devices."""
from __future__ import annotations

from abc import abstractmethod

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .router import NetgearRouter


class NetgearDeviceEntity(CoordinatorEntity):
    """Base class for a device connected to a Netgear router."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DataUpdateCoordinator, router: NetgearRouter, device: dict
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator)
        self._router = router
        self._device = device
        self._mac = device["mac"]
        self._device_name = self.get_device_name()
        self._active = device["active"]
        self._attr_unique_id = self._mac
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac)},
            default_name=self._device_name,
            default_model=device["device_model"],
            via_device=(DOMAIN, router.unique_id),
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


class NetgearRouterEntity(Entity):
    """Base class for a Netgear router entity without coordinator."""

    _attr_has_entity_name = True

    def __init__(self, router: NetgearRouter) -> None:
        """Initialize a Netgear device."""
        self._router = router

        configuration_url = None
        if host := router.entry.data[CONF_HOST]:
            configuration_url = f"http://{host}/"

        self._attr_unique_id = router.serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, router.unique_id)},
            manufacturer="Netgear",
            name=router.device_name,
            model=router.model,
            sw_version=router.firmware_version,
            hw_version=router.hardware_version,
            configuration_url=configuration_url,
        )


class NetgearRouterCoordinatorEntity(NetgearRouterEntity, CoordinatorEntity):
    """Base class for a Netgear router entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, router: NetgearRouter
    ) -> None:
        """Initialize a Netgear device."""
        CoordinatorEntity.__init__(self, coordinator)
        NetgearRouterEntity.__init__(self, router)

    @abstractmethod
    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_update_device()
        super()._handle_coordinator_update()
