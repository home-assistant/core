"""Select platform for the KWB Modbus integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KwbModbusConfigEntry
from .const import (
    CONF_DISCOVERED_SENSORS,
    CONF_EXPERT_MODE,
    CONF_HEATING_DEVICE,
    DOMAIN,
    EXPERT_SELECT_ADDRESSES,
    HEATING_DEVICES,
)
from .coordinator import KWBDataUpdateCoordinator
from .register_map import VALUE_TABLES, SelectRegisterDef


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwbModbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KWB Modbus select entities."""
    coordinator: KWBDataUpdateCoordinator = entry.runtime_data
    expert_mode: bool = entry.data.get(CONF_EXPERT_MODE, False)
    discovered: dict[str, bool] = entry.data.get(CONF_DISCOVERED_SENSORS, {})

    # Build set of indices that were confirmed active during discovery.
    # If any sensor with a given index (e.g. "HC 1.1") was discovered as enabled,
    # the corresponding select entities for that index should be enabled too.
    active_indices: set[str] = {
        r.index
        for r in coordinator.get_all_registers()
        if r.index and discovered.get(f"kwb_{r.address}", True)
    }

    entities = [
        KWBSelectEntity(coordinator, register, entry, expert_mode, active_indices)
        for register in coordinator.get_all_select_registers()
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
        active_indices: set[str],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._register = register
        self._entry = entry
        self._attr_unique_id = f"kwb_select_{register.address}"

        self._attr_name = (
            f"{register.index} {register.name}".strip()
            if register.index else register.name
        )

        table = VALUE_TABLES.get(register.value_table, {})
        self._table: dict[int, str] = table
        self._reverse_table: dict[str, int] = {v: k for k, v in table.items()}
        self._attr_options = list(table.values())
        self._attr_current_option: str | None = None

        if register.address in EXPERT_SELECT_ADDRESSES:
            self._attr_entity_category = EntityCategory.CONFIG
            self._attr_entity_registry_enabled_default = expert_mode
        elif register.index:
            # Indexed selects (HC, BUF, …): only enable when expert mode is on
            # AND the circuit was confirmed active during discovery.
            self._attr_entity_registry_enabled_default = (
                expert_mode and register.index in active_indices
            )
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
        """Return device information."""
        host = self._entry.data.get(CONF_HOST, "unknown")
        model = HEATING_DEVICES.get(
            self._entry.data.get(CONF_HEATING_DEVICE, ""), "KWB Heating"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"KWB Heating ({host})",
            manufacturer="KWB",
            model=model,
        )
