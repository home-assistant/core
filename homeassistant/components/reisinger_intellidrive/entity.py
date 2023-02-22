"""Entity for the reisinger intellidrive component."""
from __future__ import annotations

from abc import abstractmethod

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUSDICT_SERIALNO, STATUSDICT_VERSION
from .coordinator import IntellidriveCoordinator


class IntelliDriveEntity(CoordinatorEntity[IntellidriveCoordinator]):
    """Representation of a IntelliDrive entity, which is used as a base entity for future entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntellidriveCoordinator,
        device_id: str,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""

        if description is not None:
            self.entity_description = description
            self._attr_unique_id = f"{device_id}_{description.key}"
        else:
            self._attr_unique_id = device_id

        self._device_id = device_id

        super().__init__(coordinator)
        self._update_attr()

    @abstractmethod
    @callback
    def _update_attr(self) -> None:
        """Update the state and attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            configuration_url=f"http://{self.coordinator.device.host}",
            connections={
                (CONNECTION_NETWORK_MAC, self.coordinator.data[STATUSDICT_SERIALNO])
            },
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Reisinger GmbH",
            name=self.coordinator.device.host,
            sw_version=self.coordinator.data[STATUSDICT_VERSION],
        )
