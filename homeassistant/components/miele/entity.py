"""Entity base class for the Miele integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, StateStatus
from .coordinator import MieleDataUpdateCoordinator


class MieleEntity(CoordinatorEntity[MieleDataUpdateCoordinator]):
    """Base class for Miele entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}-{self.entity_description.key}"

        device = self.coordinator.data.devices[self._device_id]
        appliance_type = device.device_type_localized
        if appliance_type == "":
            appliance_type = device.tech_type

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            serial_number=self._device_id,
            name=appliance_type,
            manufacturer=MANUFACTURER,
            model=device.tech_type,
            hw_version=device.xkm_tech_type,
            sw_version=device.xkm_release_version,
        )

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""

        if not self.coordinator.last_update_success:
            return False

        return (
            self.coordinator.data.devices[self._device_id].state_status
            != StateStatus.NOT_CONNECTED
        )
