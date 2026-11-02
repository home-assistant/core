"""Select platform for the Seafile integration."""

from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_LIBRARY_ID, SUBENTRY_TYPE_LIBRARY
from .coordinator import SeafileConfigEntry
from .entity import SeafileEntity
from .utils import handle_seafile_errors

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
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIBRARY):
        # Only owned libraries on servers that allow the setting have a history limit.
        if subentry.data[CONF_LIBRARY_ID] not in coordinator.data.history_limits:
            continue
        async_add_entities(
            [SeafileHistorySelect(coordinator, subentry, HISTORY_DESCRIPTION)],
            config_subentry_id=subentry.subentry_id,
        )


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
        async with handle_seafile_errors():
            keep_days = await self.coordinator.client.set_library_history_limit(
                self.library_id, keep_days
            )
        self.coordinator.data.history_limits[self.library_id] = keep_days
        self.async_write_ha_state()
