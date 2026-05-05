"""Number platform for Zeversolar — proportional power limit slider."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MINIMUM_LIMIT
from .coordinator import ZeversolarConfigEntry, ZeversolarCoordinator
from .entity import ZeversolarEntity
from .ramp import async_ramp


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZeversolarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zeversolar number entity."""
    coordinator: ZeversolarCoordinator = entry.runtime_data
    async_add_entities([ZeversolarPowerLimitNumber(coordinator)])


class ZeversolarPowerLimitNumber(ZeversolarEntity, NumberEntity):
    """Slider that sets the active power limit on the inverter.

    Range: MINIMUM_LIMIT (5%) – 100%
    Moving the slider triggers an async ramp; the value updates in real time
    as each step completes.
    """

    _attr_translation_key = "power_limit"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = MINIMUM_LIMIT
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:transmission-tower-export"

    def __init__(self, coordinator: ZeversolarCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = (
            f"{coordinator.data['inverter_data'].serial_number}_power_limit_control"
        )

    @property
    def available(self) -> bool:
        """Unavailable if API unsupported or a ramp is in progress."""
        return (
            super().available
            and self.coordinator.power_limit_supported
            and not self.coordinator.ramp_lock.locked()
        )

    @property
    def native_value(self) -> int:
        """Return the current power limit."""
        return self.coordinator.data["power_limit"]

    async def async_set_native_value(self, value: float) -> None:
        """Ramp to the requested value."""
        if self.coordinator.ramp_lock.locked():
            return

        target = int(value)

        async def on_step(v: int) -> None:
            self.coordinator.async_set_updated_data(
                {**self.coordinator.data, "power_limit": v}
            )

        async with self.coordinator.ramp_lock:
            # Notify listeners immediately so the slider shows unavailable
            # while the ramp is in progress (availability checks ramp_lock).
            self.coordinator.async_set_updated_data(self.coordinator.data)
            await async_ramp(self.hass, self.coordinator.host, target, on_step)

        await self.coordinator.async_request_refresh()
