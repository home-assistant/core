"""Entity base class for the Miele integration."""

from pymiele import MieleAction, MieleDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AsyncConfigEntryAuth
from .const import DEVICE_TYPE_TAGS, DOMAIN, MANUFACTURER, MieleAppliance, StateStatus
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
        self._attr_unique_id = f"{device_id}-{description.key}"

        device = self.device
        appliance_type = DEVICE_TYPE_TAGS.get(MieleAppliance(device.device_type))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            serial_number=device_id,
            name=appliance_type or device.tech_type,
            translation_key=appliance_type,
            manufacturer=MANUFACTURER,
            model=device.tech_type,
            hw_version=device.xkm_tech_type,
            sw_version=device.xkm_release_version,
        )

    @property
    def device(self) -> MieleDevice:
        """Return the device object."""
        return self.coordinator.data.devices[self._device_id]

    @property
    def action(self) -> MieleAction:
        """Return the actions object."""
        return self.coordinator.data.actions[self._device_id]

    @property
    def api(self) -> AsyncConfigEntryAuth:
        """Return the api object."""
        return self.coordinator.api

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""

        return (
            super().available
            and self._device_id in self.coordinator.data.devices
            and (self.device.state_status is not StateStatus.NOT_CONNECTED)
        )
