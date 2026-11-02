"""Number platform for the Seafile integration."""

from typing import override

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_LIBRARY_ID, SUBENTRY_TYPE_LIBRARY
from .coordinator import SeafileConfigEntry
from .entity import SeafileEntity

PARALLEL_UPDATES = 0

HISTORY_DAYS_DESCRIPTION = NumberEntityDescription(
    key="history_days",
    translation_key="history_days",
    entity_category=EntityCategory.CONFIG,
    native_min_value=1,
    native_max_value=3650,
    native_step=1,
    native_unit_of_measurement=UnitOfTime.DAYS,
    mode=NumberMode.BOX,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeafileConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Seafile numbers."""
    coordinator = entry.runtime_data
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIBRARY):
        if subentry.data[CONF_LIBRARY_ID] not in coordinator.data.history_limits:
            continue
        async_add_entities(
            [SeafileHistoryDaysNumber(coordinator, subentry, HISTORY_DAYS_DESCRIPTION)],
            config_subentry_id=subentry.subentry_id,
        )


class SeafileHistoryDaysNumber(SeafileEntity, NumberEntity):
    """Set for how many days a Seafile library keeps its history."""

    @property
    @override
    def available(self) -> bool:
        """Return if the library keeps a period of history."""
        return (
            super().available
            and self.coordinator.data.history_limits.get(self.library_id, 0) > 0
        )

    @property
    @override
    def native_value(self) -> int:
        """Return the days of history the library keeps."""
        return self.coordinator.data.history_limits[self.library_id]

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Change the days of history the library keeps."""
        await self.coordinator.async_set_history_limit(self.library_id, int(value))
