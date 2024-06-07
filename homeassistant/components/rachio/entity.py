"""Adapter to wrap the rachiopy api for home assistant."""

from abc import abstractmethod
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    KEY_BATTERY_STATUS,
    KEY_CONNECTED,
    KEY_CURRENT_STATUS,
    KEY_FLOW_DETECTED,
    KEY_ID,
    KEY_LOW,
    KEY_NAME,
    KEY_REPLACE,
    KEY_REPORTED_STATE,
    KEY_STATE,
)
from .coordinator import RachioUpdateCoordinator
from .device import RachioIro


class RachioDevice(Entity):
    """Base class for rachio devices."""

    _attr_should_poll = False

    def __init__(self, controller: RachioIro) -> None:
        """Initialize a Rachio device."""
        super().__init__()
        self._controller = controller
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self._controller.serial_number,
                )
            },
            connections={
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._controller.mac_address,
                )
            },
            name=self._controller.name,
            model=self._controller.model,
            manufacturer=DEFAULT_NAME,
            configuration_url="https://app.rach.io",
        )


class RachioHoseTimerEntity(CoordinatorEntity[RachioUpdateCoordinator]):
    """Base class for smart hose timer entities."""

    _attr_has_entity_name = True

    def __init__(
        self, data: dict[str, Any], coordinator: RachioUpdateCoordinator
    ) -> None:
        """Initialize a Rachio smart hose timer entity."""
        super().__init__(coordinator)
        self.id = data[KEY_ID]
        self._name = data[KEY_NAME]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.id)},
            model="Smart Hose Timer",
            name=self._name,
            manufacturer=DEFAULT_NAME,
            configuration_url="https://app.rach.io",
        )

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            super().available
            and self.coordinator.data[self.id][KEY_STATE][KEY_REPORTED_STATE][
                KEY_CONNECTED
            ]
        )

    @property
    def battery(self) -> bool:
        """Return the battery status."""
        return self.coordinator.data[self.id][KEY_STATE][KEY_REPORTED_STATE][
            KEY_BATTERY_STATUS
        ] in [
            KEY_LOW,
            KEY_REPLACE,
        ]

    @property
    def flow_detected(self) -> bool:
        """Return true if valve is on and flow is not detected."""
        status = self.coordinator.data[self.id][KEY_STATE][KEY_REPORTED_STATE].get(
            KEY_CURRENT_STATUS
        )
        if status:
            return not status.get(
                KEY_FLOW_DETECTED, True
            )  # Since this is a problem indicator we need the opposite of the API state
        return False

    @abstractmethod
    def _update_attr(self) -> None:
        """Update the state and attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        super()._handle_coordinator_update()
