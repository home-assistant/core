"""Select platform for the Seafile integration."""

from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_LIBRARY_ID, SUBENTRY_TYPE_LIBRARY
from .coordinator import SeafileConfigEntry
from .entity import SeafileEntity

PARALLEL_UPDATES = 0

HISTORY_KEEP_ALL = "keep_all"
HISTORY_KEEP_NONE = "keep_none"
HISTORY_LIMITED = "limited"
# Seafile stores -1 for full history and 0 for no history.
KEEP_DAYS_ALL = -1
KEEP_DAYS_NONE = 0
DEFAULT_KEEP_DAYS = 30

HISTORY_DESCRIPTION = SelectEntityDescription(
    key="history",
    translation_key="history",
    entity_category=EntityCategory.CONFIG,
    options=[HISTORY_KEEP_ALL, HISTORY_KEEP_NONE, HISTORY_LIMITED],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeafileConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Seafile selects."""
    coordinator = entry.runtime_data
    added_subentry_ids: set[str] = set()

    @callback
    def _async_add_history_selects() -> None:
        """Add a select for each library that has a history limit."""
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIBRARY):
            # Only libraries the account owns or administers have a history limit.
            if (
                subentry.subentry_id in added_subentry_ids
                or subentry.data[CONF_LIBRARY_ID] not in coordinator.data.history_limits
            ):
                continue
            added_subentry_ids.add(subentry.subentry_id)
            async_add_entities(
                [SeafileHistorySelect(coordinator, subentry, HISTORY_DESCRIPTION)],
                config_subentry_id=subentry.subentry_id,
            )

    _async_add_history_selects()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_history_selects))


class SeafileHistorySelect(SeafileEntity, SelectEntity):
    """Select how much history a Seafile library keeps."""

    @property
    @override
    def available(self) -> bool:
        """Return if the history setting of the library is known."""
        return (
            super().available
            and self.library_id in self.coordinator.data.history_limits
        )

    @property
    @override
    def current_option(self) -> str:
        """Return the history mode of the library."""
        keep_days = self.coordinator.data.history_limits[self.library_id]
        if keep_days < 0:
            return HISTORY_KEEP_ALL
        if keep_days == KEEP_DAYS_NONE:
            return HISTORY_KEEP_NONE
        return HISTORY_LIMITED

    @override
    async def async_select_option(self, option: str) -> None:
        """Change how much history the library keeps."""
        if option == HISTORY_LIMITED and self.current_option == HISTORY_LIMITED:
            return
        keep_days = {
            HISTORY_KEEP_ALL: KEEP_DAYS_ALL,
            HISTORY_KEEP_NONE: KEEP_DAYS_NONE,
            HISTORY_LIMITED: DEFAULT_KEEP_DAYS,
        }[option]
        await self.coordinator.async_set_history_limit(self.library_id, keep_days)
