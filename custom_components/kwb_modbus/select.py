"""Select platform for the KWB Modbus integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KwbModbusConfigEntry
from .const import (
    CONF_ACTIVE_INSTANCES,
    CONF_EXPERT_MODE,
    CONF_HEATING_DEVICE,
    CONF_INSTANCE_NAMES,
    CONFIG_SELECT_PARAMS,
    DOMAIN,
    EXPERT_SELECT_ADDRESSES,
    HEATING_DEVICES,
    MODBUS_HOLDING_REG_START,
)
from .coordinator import KWBDataUpdateCoordinator
from .entity_translations import param_to_translation_key
from .register_maps.types import SelectRegisterDef


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwbModbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KWB Modbus select entities."""
    coordinator: KWBDataUpdateCoordinator = entry.runtime_data
    expert_mode: bool = entry.data.get(CONF_EXPERT_MODE, False)

    # Collect all explicitly selected instance labels (e.g. "HC 1.1", "BUF 0")
    # from the user's setup configuration.
    active_instances: dict[str, list[str]] = entry.data.get(CONF_ACTIVE_INSTANCES, {})
    active_indices: set[str] = {
        instance
        for instances in active_instances.values()
        for instance in instances
    }

    # Flat lookup: instance_label → friendly_name
    instance_names: dict[str, str] = {
        inst: name
        for names in entry.data.get(CONF_INSTANCE_NAMES, {}).values()
        for inst, name in names.items()
    }

    writable_select_keys: set[tuple[str, int, str, str]] = set()
    for module_key in coordinator.get_all_module_keys():
        for register in coordinator.get_registers_for_module(module_key):
            if (
                register.address < MODBUS_HOLDING_REG_START
                or register.is_status
                or not register.value_table
                or not register.writable
            ):
                continue
            writable_select_keys.add(
                (module_key, register.address, register.param, register.index or "")
            )

    existing = [
        register
        for register in coordinator.get_all_select_registers()
        if (register.module, register.address, register.param, register.index or "")
        in writable_select_keys
    ]
    existing_keys = {
        (s.module, s.address, s.param, s.index or "") for s in existing
    }
    auto_generated: list[SelectRegisterDef] = []
    for module_key in coordinator.get_all_module_keys():
        for register in coordinator.get_registers_for_module(module_key):
            if (
                register.address < MODBUS_HOLDING_REG_START
                or register.is_status
                or not register.value_table
                or not register.writable
            ):
                continue
            key = (
                module_key,
                register.address,
                register.param,
                register.index or "",
            )
            if key in existing_keys:
                continue
            auto_generated.append(
                SelectRegisterDef(
                    address=register.address,
                    name=register.name,
                    param=register.param,
                    index=register.index,
                    value_table=register.value_table,
                    data_type=register.data_type,
                    module=module_key,
                )
            )

    entities = [
        KWBSelectEntity(coordinator, register, entry, expert_mode, instance_names)
        for register in [*existing, *auto_generated]
        if not register.index or register.index in active_indices
    ]
    async_add_entities(entities)


class KWBSelectEntity(CoordinatorEntity[KWBDataUpdateCoordinator], SelectEntity):
    """Select entity for a writable KWB Modbus holding register."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KWBDataUpdateCoordinator,
        register: SelectRegisterDef,
        entry: KwbModbusConfigEntry,
        expert_mode: bool,
        instance_names: dict[str, str] | None = None,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._register = register
        self._entry = entry
        self._instance_names = instance_names or {}
        self._attr_unique_id = f"{entry.entry_id}_select_{register.address}"
        self._attr_translation_key = param_to_translation_key(register.param)

        table = coordinator.get_value_table(register.value_table)
        self._table: dict[int, str] = table
        self._reverse_table: dict[str, int] = {v: k for k, v in table.items()}
        self._attr_options = list(table.values())
        self._attr_current_option: str | None = None

        if register.address in EXPERT_SELECT_ADDRESSES:
            self._attr_entity_category = EntityCategory.CONFIG
            self._attr_entity_registry_enabled_default = expert_mode
        elif register.param in CONFIG_SELECT_PARAMS:
            self._attr_entity_category = EntityCategory.CONFIG
            self._attr_entity_registry_enabled_default = True
        else:
            self._attr_entity_registry_enabled_default = True

    async def async_added_to_hass(self) -> None:
        """Fetch initial value when entity is added."""
        await super().async_added_to_hass()
        await self._async_refresh_value()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh holding register value on each coordinator cycle."""
        self.hass.async_create_task(self._async_refresh_value())

    async def _async_refresh_value(self) -> None:
        """Read current value from the holding register and update state."""
        raw = await self.coordinator.async_read_holding_register(
            self._register.address
        )
        self._attr_current_option = self._table.get(raw) if raw is not None else None
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Write selected option to holding register."""
        value = self._reverse_table.get(option)
        if value is None:
            return
        success = await self.coordinator.async_write_holding_register(
            self._register.address, value
        )
        if success:
            self._attr_current_option = option
            self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information.

        Indexed entities (HC, BUF, SOL, ...) are attached to a per-instance
        sub-device linked to the main KWB boiler device via via_device.
        Non-indexed entities live directly on the main device.
        """
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
