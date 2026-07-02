"""Number platform for writable KWB Modbus holding registers."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KwbModbusConfigEntry
from .const import (
    CONF_ACTIVE_INSTANCES,
    CONF_HEATING_DEVICE,
    CONF_INSTANCE_NAMES,
    DOMAIN,
    HEATING_DEVICES,
    MODBUS_HOLDING_REG_START,
)
from .coordinator import KWBDataUpdateCoordinator
from .entity_translations import param_to_translation_key
from .register_maps.types import RegisterDef


def _encode_16(value: int, data_type: str) -> int | None:
    """Encode signed/unsigned 16-bit value to raw Modbus word."""
    if data_type == "s16":
        if value < -32768 or value > 32767:
            return None
        return value & 0xFFFF
    if data_type == "u16":
        if value < 0 or value > 0xFFFF:
            return None
        return value
    return None


def _encode_32(value: int, data_type: str) -> int | None:
    """Encode signed/unsigned 32-bit value to raw Modbus dword."""
    if data_type == "s32":
        if value < -2147483648 or value > 2147483647:
            return None
        return value & 0xFFFFFFFF
    if data_type == "u32":
        if value < 0 or value > 0xFFFFFFFF:
            return None
        return value
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwbModbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KWB Modbus number entities."""
    coordinator: KWBDataUpdateCoordinator = entry.runtime_data

    active_instances: dict[str, list[str]] = entry.data.get(CONF_ACTIVE_INSTANCES, {})
    active_indices: set[str] = {
        instance
        for instances in active_instances.values()
        for instance in instances
    }
    instance_names: dict[str, str] = {
        inst: name
        for names in entry.data.get(CONF_INSTANCE_NAMES, {}).values()
        for inst, name in names.items()
    }

    entities: list[KWBNumberEntity] = []
    seen_addresses: set[int] = set()
    for module_key in coordinator.get_all_module_keys():
        for register in coordinator.get_registers_for_module(module_key):
            if (
                register.address < MODBUS_HOLDING_REG_START
                or register.is_status
                or register.value_table
                or not register.writable
            ):
                continue
            # Some optional modules expose shared technical holding registers.
            # Avoid duplicate entities and unique_id collisions.
            if register.address in seen_addresses:
                continue
            if register.index and register.index not in active_indices:
                continue
            seen_addresses.add(register.address)
            entities.append(KWBNumberEntity(coordinator, register, entry, instance_names))

    async_add_entities(entities)


class KWBNumberEntity(CoordinatorEntity[KWBDataUpdateCoordinator], NumberEntity):
    """Number entity for writable numeric KWB holding registers."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        coordinator: KWBDataUpdateCoordinator,
        register: RegisterDef,
        entry: KwbModbusConfigEntry,
        instance_names: dict[str, str] | None = None,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._register = register
        self._entry = entry
        self._instance_names = instance_names or {}
        self._attr_unique_id = f"{entry.entry_id}_number_{register.address}"
        self._attr_translation_key = param_to_translation_key(register.param)
        self._attr_native_unit_of_measurement = register.unit or None

        scale = register.scale or 1.0
        self._attr_native_step = min(1, scale)

        if register.data_type == "s16":
            self._attr_native_min_value = -32768 * scale
            self._attr_native_max_value = 32767 * scale
        elif register.data_type == "u16":
            self._attr_native_min_value = 0
            self._attr_native_max_value = 65535 * scale
        elif register.data_type == "s32":
            self._attr_native_min_value = -2147483648 * scale
            self._attr_native_max_value = 2147483647 * scale
        elif register.data_type == "u32":
            self._attr_native_min_value = 0
            self._attr_native_max_value = 4294967295 * scale

    @property
    def native_value(self) -> float | None:
        """Return current numeric value."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self._register.address)
        if value is None:
            return None
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Write numeric value to holding register(s)."""
        scale = self._register.scale or 1.0
        raw = int(round(value / scale))

        success = False
        if self._register.count == 1:
            encoded = _encode_16(raw, self._register.data_type)
            if encoded is None:
                return
            success = await self.coordinator.async_write_holding_register(
                self._register.address, encoded
            )
        elif self._register.count == 2:
            encoded = _encode_32(raw, self._register.data_type)
            if encoded is None:
                return
            words = [(encoded >> 16) & 0xFFFF, encoded & 0xFFFF]
            success = await self.coordinator.async_write_holding_registers(
                self._register.address, words
            )

        if success:
            await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        """Return extra state attributes."""
        return {
            "modbus_address": self._register.address,
            "kwb_parameter": self._register.param,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        if self._register.index:
            friendly_name = self._instance_names.get(
                self._register.index, self._register.index
            )
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._register.index}")},
                name=friendly_name,
                via_device=(DOMAIN, self._entry.entry_id),
                manufacturer="KWB",
            )
        model = HEATING_DEVICES.get(
            self._entry.data.get(CONF_HEATING_DEVICE, ""), "KWB Heating"
        )
        data = self.coordinator.data or {}
        major, minor, patch = data.get(8192), data.get(8193), data.get(8194)
        sw_version = (
            f"{major}.{minor}.{patch}" if None not in (major, minor, patch) else None
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=model,
            manufacturer="KWB",
            model=model,
            sw_version=sw_version,
        )
