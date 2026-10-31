"""Button platform for the Seafile integration."""

from typing import override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SUBENTRY_TYPE_LIBRARY
from .coordinator import SeafileConfigEntry
from .entity import SeafileEntity
from .utils import handle_seafile_errors

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeafileConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Seafile buttons."""
    coordinator = entry.runtime_data
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIBRARY):
        async_add_entities(
            [
                SeafileEmptyTrashButton(
                    coordinator,
                    subentry,
                    ButtonEntityDescription(
                        key="empty_trash", translation_key="empty_trash"
                    ),
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SeafileEmptyTrashButton(SeafileEntity, ButtonEntity):
    """Button to empty the trash of a Seafile library."""

    @override
    @handle_seafile_errors()
    async def async_press(self) -> None:
        """Permanently delete the items in the trash of the library."""
        await self.coordinator.client.clean_library_trash(self.library_id)
