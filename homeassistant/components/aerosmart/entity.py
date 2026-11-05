"""Base entity for aerosmart.

One HA device represents the whole installation (both Modbus units); this
integration does not split ventilation/heat-pump into separate devices.
"""

from dataclasses import dataclass
from typing import override

from aerosmart_modbus import WriteVerificationError
from modbus_connection import ModbusError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AerosmartCoordinator


@dataclass(frozen=True, kw_only=True)
class AerosmartEntityDescription(EntityDescription):
    """Describes an aerosmart entity backed by a device component attribute."""

    component: str
    attribute: str


class AerosmartEntity(CoordinatorEntity[AerosmartCoordinator]):
    """Common identity, device-info and register access for aerosmart entities."""

    entity_description: AerosmartEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AerosmartCoordinator,
        entity_description: AerosmartEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"
        device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="aerosmart",
        )
        general = coordinator.device.general
        if (device_type := general.device_type) is not None:
            device_info["model"] = str(device_type)
        if (software_version := general.software_version) is not None:
            device_info["sw_version"] = str(software_version)
        self._attr_device_info = device_info

    @property
    @override
    def available(self) -> bool:
        """Return whether this entity's own subsystem refreshed."""
        return (
            super().available
            and self.entity_description.component in self.coordinator.data.updated
        )

    async def _async_write_verified(self, value: object) -> None:
        """Write and confirm a manufacturer-verified control value."""
        description = self.entity_description
        try:
            await self.coordinator.device.async_write_verified(
                description.component, description.attribute, value
            )
        except (ModbusError, WriteVerificationError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={
                    "field": description.key,
                    "error": str(err),
                },
            ) from err
        self.coordinator.async_update_listeners()
