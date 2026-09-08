"""Represent the Netgear router and its devices."""

from abc import abstractmethod
from typing import Any, override

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetgearDataCoordinator, NetgearTrackerCoordinator
from .router import NetgearRouter


class NetgearDeviceEntity(CoordinatorEntity[NetgearTrackerCoordinator]):
    """Base class for a device connected to a Netgear router."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetgearTrackerCoordinator,
        device: dict,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator)
        self._router = coordinator.router
        self._device = device
        self._mac = device["mac"]
        self._device_name = self.get_device_name()
        self._active = device["active"]
        self._attr_unique_id = self._mac
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac)},
            name=self._device_name,
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, coordinator.router.unique_id),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
        )
        # Offline devices restored at startup have no model yet; only set it when known
        # so a previously stored model is not overwritten with None.
        if (device_model := device["device_model"]) is not None:
            self._attr_device_info["model"] = device_model

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
    @override
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
        self._attr_unique_id = router.serial_number
        self._attr_device_info = router.device_info


class NetgearRouterCoordinatorEntity[T: NetgearDataCoordinator[Any]](
    NetgearRouterEntity, CoordinatorEntity[T]
):
    """Base class for a Netgear router entity."""

    def __init__(self, coordinator: T) -> None:
        """Initialize a Netgear device."""
        CoordinatorEntity.__init__(self, coordinator)
        NetgearRouterEntity.__init__(self, coordinator.router)

    @abstractmethod
    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_update_device()
        super()._handle_coordinator_update()
