"""Entity for the opengarage.io component."""

from collections.abc import Callable
from typing import override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenGarageDataUpdateCoordinator


class OpenGarageEntity(CoordinatorEntity[OpenGarageDataUpdateCoordinator]):
    """Representation of a OpenGarage entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        open_garage_data_coordinator: OpenGarageDataUpdateCoordinator,
        device_id: str,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(open_garage_data_coordinator)

        if description is not None:
            self.entity_description = description
            self._attr_unique_id = f"{device_id}_{description.key}"
        else:
            self._attr_unique_id = device_id

        self._device_id = device_id
        self._update_attr()

    @callback
    def _update_attr(self) -> None:
        """Update the state and attributes."""

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            configuration_url=self.coordinator.open_garage_connection.device_url,
            connections={(CONNECTION_NETWORK_MAC, self.coordinator.data.raw["mac"])},
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Open Garage",
            name=self.coordinator.data.raw["name"],
            suggested_area="Garage",
            sw_version=str(self.coordinator.data.raw["fwv"]),
        )


@callback
def async_add_capability_entities(
    coordinator: OpenGarageDataUpdateCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factories: dict[str, Callable[[], Entity]],
) -> None:
    """Discover optional entities initially and when capabilities appear."""
    added: set[str] = set()

    @callback
    def async_check_capabilities() -> None:
        entities = []
        for capability, factory in factories.items():
            if capability not in added and coordinator.data.capabilities[capability]:
                added.add(capability)
                entities.append(factory())
        if entities:
            async_add_entities(entities)

    async_check_capabilities()
    coordinator.config_entry.async_on_unload(
        coordinator.async_add_listener(async_check_capabilities)
    )


class OpenGarageCapabilityEntity(OpenGarageEntity):
    """An entity that is available while its capability is reported."""

    capability: str

    @property
    @override
    def available(self) -> bool:
        """Return whether this device still provides the capability."""
        return super().available and self.coordinator.data.capabilities[self.capability]
