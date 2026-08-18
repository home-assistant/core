"""Switch platform: whether the active power control limit is armed.

Register 1105's Bit0 must go out with 1106's limit percentage, so this stages a bool in coordinator.pending instead of writing on toggle — a paired button (follow-up PR) commits both together.
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
    """The enabled state this switch is currently showing — pending or live. Shared with the button platform (follow-up PR) so its commit uses this exact value."""
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
