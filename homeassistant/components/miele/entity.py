"""Entity base class for the Miele integration."""

from pymiele import MieleAction, MieleAPI, MieleDevice, MieleFillingLevel

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_TYPE_TAGS, DOMAIN, MANUFACTURER, MieleAppliance, StateStatus
from .coordinator import MieleAuxDataUpdateCoordinator, MieleDataUpdateCoordinator


class MieleBaseEntity[
    _MieleCoordinatorT: MieleDataUpdateCoordinator | MieleAuxDataUpdateCoordinator
](CoordinatorEntity[_MieleCoordinatorT]):
    """Base class for Miele entities."""

    _attr_has_entity_name = True

    @staticmethod
    def get_unique_id(device_id: str, description: EntityDescription) -> str:
        """Generate a unique ID for the entity."""
        return f"{device_id}-{description.key}"

    def __init__(
        self,
        coordinator: _MieleCoordinatorT,
        device_id: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self.entity_description = description
        self._attr_unique_id = MieleBaseEntity.get_unique_id(device_id, description)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def api(self) -> MieleAPI:
        """Return the api object."""
        return self.coordinator.api


class MieleEntity(MieleBaseEntity[MieleDataUpdateCoordinator]):
    """Base class for Miele entities that use the main data coordinator."""

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, device_id, description)

        device = self.device
        appliance_type = DEVICE_TYPE_TAGS.get(MieleAppliance(device.device_type))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            serial_number=device_id,
            name=device.device_name or appliance_type or device.tech_type,
            translation_key=None if device.device_name else appliance_type,
            manufacturer=MANUFACTURER,
            model=(
                appliance_type.capitalize().replace("_", " ")
                if appliance_type
                else None
            )
            or device.tech_type,
            model_id=device.tech_type,
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
    def available(self) -> bool:
        """Return the availability of the entity."""

        return (
            super().available
            and self._device_id in self.coordinator.data.devices
            and (self.device.state_status is not StateStatus.not_connected)
        )


class MieleAuxEntity(MieleBaseEntity[MieleAuxDataUpdateCoordinator]):
    """Base class for Miele entities that use the auxiliary data coordinator."""

    @property
    def levels(self) -> MieleFillingLevel:
        """Return the filling levels object."""
        return self.coordinator.data.filling_levels[self._device_id]
