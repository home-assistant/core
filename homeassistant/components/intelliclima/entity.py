"""Platform for shared base classes for sensors."""

from pyintelliclima import IntelliClimaC800, IntelliClimaECO

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntelliClimaCoordinator


class IntelliClimaEntity(CoordinatorEntity[IntelliClimaCoordinator]):
    """Define a generic class for IntelliClima entities."""

    _attr_attribution = "Data provided by unpublished IntelliClima API"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO | IntelliClimaC800,
        description: EntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"

        # Make this HA "device" use the IntelliClima device name.
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.id)},
            "name": device.name,
        }

        self._device_id = device.id
        self._device_sn = device.crono_sn
