"""Base entity for Victron Modbus devices."""

from dataclasses import dataclass
from typing import cast, override

from modbus_connection.model import Component

from homeassistant.const import CONF_MODEL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import VictronModbusCoordinator, VictronModbusData
from .models import MODELS


@dataclass(frozen=True, kw_only=True)
class VictronModbusEntityDescription(EntityDescription):
    """Describe a Victron Modbus entity."""

    sub_system: str  # the polled sub-system it is read in: power, meter or phases


class VictronModbusEntity(CoordinatorEntity[VictronModbusCoordinator]):
    """Common identity + device-info for every Victron Modbus entity."""

    _attr_has_entity_name = True
    entity_description: VictronModbusEntityDescription

    def __init__(
        self,
        data: VictronModbusData,
        description: VictronModbusEntityDescription,
        component: str,
        attribute: str,
        phase: int | None = None,
    ) -> None:
        """Initialize an entity reading ``attribute`` of library ``component``.

        ``phase`` (1 to 3) names the phase a per-phase entity measures.
        """
        super().__init__(data.coordinator_for(description.sub_system))
        self.entity_description = description
        self._component = component
        self._attribute = attribute
        entry = self.coordinator.config_entry
        serial_number = entry.unique_id
        assert serial_number is not None
        if phase is None:
            self._attr_unique_id = f"{serial_number}_{description.key}"
        else:
            self._attr_unique_id = f"{serial_number}_phase_{phase}_{description.key}"
            self._attr_translation_placeholders = {"phase": f"L{phase}"}
        hardware_version = self.coordinator.device.info.hardware_version
        model = MODELS[entry.data[CONF_MODEL]].name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer=MANUFACTURER,
            model=model,
            # The serial number is in the entry title; leaving it out of the
            # device name keeps entity IDs short, like sensor.vm_3p75ct_total_power.
            name=model,
            serial_number=serial_number,
            hw_version=None if hardware_version is None else str(hardware_version),
        )

    @property
    @override
    def available(self) -> bool:
        """Unavailable while the last poll of this entity's sub-system failed."""
        return (
            super().available
            and self.entity_description.sub_system in self.coordinator.data.updated
        )

    @property
    def _value(self) -> float | None:
        """The library value this entity reports; None when unavailable."""
        component = cast(Component, getattr(self.coordinator.device, self._component))
        value: float | None = getattr(component, self._attribute)
        return value
