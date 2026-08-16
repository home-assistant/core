"""Switch platform: whether the active power control limit is armed.

Register 1105's Bit0 has to go out together with the limit percentage in
1106 (see sofar_modbus.modern.ActivePowerControl), so this stages a plain
bool in coordinator.pending instead of writing on toggle — the paired
"Active Power Control: Update" button commits both together (added in a
follow-up PR alongside the button platform).
"""

from typing import Any, override

from sofar_modbus.modern import PowerControlFlags

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator
from .entity import SofarEntity

_KEY = "active_power_control_enabled"


def resolve_active_power_control_enabled(
    coordinator: SofarDataUpdateCoordinator,
) -> bool | None:
    """The enabled state this switch is currently showing — pending or live.

    Shared with the button platform (added in a follow-up PR) so "Active
    Power Control: Update" commits exactly what the switch displays, not a
    separately re-derived value.
    """
    flags = coordinator.device.active_power_control.power_control
    live = None if flags is None else PowerControlFlags.ACTIVE_POWER in flags
    return coordinator.pending_or_live(_KEY, live)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar Inverter Modbus switch platform."""
    coordinator = entry.runtime_data
    served = coordinator.served_components
    if "active_power_control" in served:
        async_add_entities([ActivePowerControlSwitch(coordinator)])


class ActivePowerControlSwitch(SofarEntity, SwitchEntity):
    """Active Power Control — staged; a paired button applies it."""

    _attr_translation_key = _KEY

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, _KEY, "active_power_control")

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether active power control is currently staged or live-armed."""
        return resolve_active_power_control_enabled(self.coordinator)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Stage active power control as enabled; a paired button commits it."""
        self.coordinator.pending[_KEY] = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stage active power control as disabled; a paired button commits it."""
        self.coordinator.pending[_KEY] = False
        self.async_write_ha_state()
