"""Sensor platform for the KWB Modbus integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KwbModbusConfigEntry
from .const import (
    CONF_ACTIVE_INSTANCES,
    CONF_DISCOVERED_SENSORS,
    CONF_HEATING_DEVICE,
    DIAGNOSTIC_ADDRESSES,
    DOMAIN,
    HEATING_DEVICES,
)
from .coordinator import KWBDataUpdateCoordinator
from .register_map import VALUE_TABLES, RegisterDef


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwbModbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KWB Modbus sensor entities."""
    coordinator: KWBDataUpdateCoordinator = entry.runtime_data
    discovered: dict[str, bool] = entry.data.get(CONF_DISCOVERED_SENSORS, {})

    # Only create sensor entities for instances the user explicitly configured.
    # Non-indexed sensors (index=None) are always included.
    active_instances: dict[str, list[str]] = entry.data.get(CONF_ACTIVE_INSTANCES, {})
    active_indices: set[str] = {
        instance
        for instances in active_instances.values()
        for instance in instances
    }

    entities = [
        KWBSensor(coordinator, r, entry, discovered.get(f"kwb_{r.address}", True))
        for r in coordinator.get_all_registers()
        if not r.index or r.index in active_indices
    ]
    async_add_entities(entities)


class KWBSensor(CoordinatorEntity[KWBDataUpdateCoordinator], SensorEntity):
    """Sensor entity for a KWB Modbus input register."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KWBDataUpdateCoordinator,
        register: RegisterDef,
        entry: KwbModbusConfigEntry,
        enabled_default: bool,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._register = register
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{register.address}"
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_name = f"{register.index} {register.name}".strip() if register.index else register.name
        if register.address in DIAGNOSTIC_ADDRESSES:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        unit = register.unit
        if register.value_table:
            # ENUM sensors must not have a unit of measurement
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(VALUE_TABLES.get(register.value_table, {}).values())
        elif unit == "°C":
            self._attr_native_unit_of_measurement = unit
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "kW":
            self._attr_native_unit_of_measurement = unit
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "kWh":
            self._attr_native_unit_of_measurement = unit
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif unit == "%":
            self._attr_native_unit_of_measurement = unit
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._register.address)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "modbus_address": self._register.address,
            "kwb_parameter": self._register.param,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        host = self._entry.data.get(CONF_HOST, "unknown")
        model = HEATING_DEVICES.get(self._entry.data.get(CONF_HEATING_DEVICE, ""), "KWB Heating")
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"KWB Heating ({host})",
            manufacturer="KWB",
            model=model,
        )
