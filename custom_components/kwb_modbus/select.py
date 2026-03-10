"""Select platform for the KWB Modbus integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KwbModbusConfigEntry
from .const import (
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

    entities = [
        KWBSelectEntity(coordinator, register, entry, expert_mode)
        for register in coordinator.get_all_select_registers()
    ]
    async_add_entities(entities, update_before_add=True)


class KWBSelectEntity(SelectEntity):
    """Select entity for a writable KWB Modbus holding register."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KWBDataUpdateCoordinator,
        register: SelectRegisterDef,
        entry: KwbModbusConfigEntry,
        expert_mode: bool,
    ) -> None:
        """Initialize the select entity."""
        self._coordinator = coordinator
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
            # Indexed circuit selects (HC, BUF, …) are only useful when expert mode is on
            self._attr_entity_registry_enabled_default = expert_mode
        else:
            self._attr_entity_registry_enabled_default = True

    async def async_update(self) -> None:
        """Read current value from holding register."""
        raw = await self._coordinator.async_read_holding_register(
            self._register.address
        )
        if raw is not None:
            self._attr_current_option = self._table.get(raw)
        else:
            self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        """Write selected option to holding register."""
        value = self._reverse_table.get(option)
        if value is None:
            return
        success = await self._coordinator.async_write_holding_register(
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
