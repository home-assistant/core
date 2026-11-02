"""Number platform for the Seafile integration."""

from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_LIBRARY_ID, SUBENTRY_TYPE_LIBRARY
from .coordinator import SeafileConfigEntry
from .entity import SeafileEntity

PARALLEL_UPDATES = 0

HISTORY_DAYS_DESCRIPTION = NumberEntityDescription(
    key="history_days",
    translation_key="history_days",
    device_class=NumberDeviceClass.DURATION,
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
    added_subentry_ids: set[str] = set()

    @callback
    def _async_add_history_days_numbers() -> None:
        """Add a number for each library that has a history limit."""
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIBRARY):
            if (
                subentry.subentry_id in added_subentry_ids
                or subentry.data[CONF_LIBRARY_ID] not in coordinator.data.history_limits
            ):
                continue
            added_subentry_ids.add(subentry.subentry_id)
            async_add_entities(
                [
                    SeafileHistoryDaysNumber(
                        coordinator, subentry, HISTORY_DAYS_DESCRIPTION
                    )
                ],
                config_subentry_id=subentry.subentry_id,
            )

    _async_add_history_days_numbers()
    entry.async_on_unload(
        coordinator.async_add_listener(_async_add_history_days_numbers)
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
