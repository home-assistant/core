"""Base entities for LinknLink."""

from typing import Any, override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LinknLinkCoordinator


class LinknLinkEntity(CoordinatorEntity[LinknLinkCoordinator]):
    """Base class for LinknLink entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LinknLinkCoordinator,
        description: EntityDescription,
        subdevice_id: str | None = None,
    ) -> None:
        """Initialize a LinknLink entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._subdevice_id = subdevice_id
        device = coordinator.device

        if subdevice_id is None:
            self._attr_unique_id = f"{device.id}_{description.key}"
            self._attr_device_info = DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
                identifiers={(DOMAIN, device.id)},
                manufacturer="LinknLink",
                model=device.model,
                name=device.name,
                serial_number=device.mac,
            )
        else:
            child = coordinator.data.children[subdevice_id]
            self._attr_unique_id = f"{device.id}_{subdevice_id}_{description.key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{device.id}_{subdevice_id}")},
                manufacturer="LinknLink",
                model=child.type or child.pid or None,
                name=child.name or child.type or subdevice_id,
                serial_number=subdevice_id,
                via_device=(DOMAIN, device.id),
            )

    @property
    def source_value(self) -> Any:
        """Return the current raw value for the entity."""
        if self._subdevice_id is None:
            return self.coordinator.data.values.get(self.entity_description.key)
        child = self.coordinator.data.children.get(self._subdevice_id)
        if child is None:
            return None
        return child.fields.get(self.entity_description.key)

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity is available."""
        if not super().available:
            return False
        if self._subdevice_id is None:
            return self.entity_description.key in self.coordinator.data.values
        child = self.coordinator.data.children.get(self._subdevice_id)
        return child is not None and self.entity_description.key in child.fields
