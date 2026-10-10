"""Number platform for Acaia scales."""

from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AcaiaConfigEntry
from .entity import AcaiaEntity

PARALLEL_UPDATES = 0

IDLE_TIMEOUT_DESCRIPTION = NumberEntityDescription(
    key="idle_timeout",
    translation_key="idle_timeout",
    entity_category=EntityCategory.CONFIG,
    device_class=NumberDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.MINUTES,
    native_min_value=0,
    native_max_value=120,
    native_step=1,
    mode=NumberMode.BOX,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AcaiaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""

    coordinator = entry.runtime_data
    async_add_entities([AcaiaIdleTimeoutNumber(coordinator, IDLE_TIMEOUT_DESCRIPTION)])


class AcaiaIdleTimeoutNumber(AcaiaEntity, NumberEntity):
    """Minutes without a weight change before disconnecting from the scale."""

    @property
    @override
    def native_value(self) -> int:
        """Return the idle timeout in minutes."""
        return self.coordinator.idle_timeout

    @property
    @override
    def available(self) -> bool:
        """This setting applies while disconnected, so it stays available."""
        return self.coordinator.last_update_success

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the idle timeout."""
        await self.coordinator.async_set_idle_timeout(int(value))
        self.async_write_ha_state()
