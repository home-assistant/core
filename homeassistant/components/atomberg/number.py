"""Number platform for Atomberg water purifiers."""

from typing import override

from atomberg_api import (
    COMMAND_TDS_THRESHOLD,
    DEVICE_TYPE_WATER_PURIFIER,
    AtombergDevice,
)

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfRatio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TDS_THRESHOLD_RANGE
from .coordinator import AtombergConfigEntry, AtombergCoordinator
from .entity import AtombergEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtombergConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Atomberg numbers."""
    coordinator = entry.runtime_data
    async_add_entities(
        AtombergTdsThresholdNumber(coordinator, device)
        for device in coordinator.devices_of_type(DEVICE_TYPE_WATER_PURIFIER)
        if coordinator.supports_setting(device, COMMAND_TDS_THRESHOLD)
    )


class AtombergTdsThresholdNumber(AtombergEntity, NumberEntity):
    """Input TDS level that decides between RO and UF treatment."""

    _attr_translation_key = "tds_threshold"
    _attr_native_min_value, _attr_native_max_value = TDS_THRESHOLD_RANGE
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfRatio.PARTS_PER_MILLION

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, device, COMMAND_TDS_THRESHOLD)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the threshold."""
        return self.device_state.get(COMMAND_TDS_THRESHOLD)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the threshold."""
        threshold = int(value)
        await self._async_send(
            {COMMAND_TDS_THRESHOLD: threshold}, {COMMAND_TDS_THRESHOLD: threshold}
        )
