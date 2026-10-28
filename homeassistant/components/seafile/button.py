"""Button platform for the Seafile integration."""

from typing import override

from aioseafile import SeafileError, SeafilePermissionError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SUBENTRY_TYPE_LIBRARY
from .coordinator import SeafileConfigEntry, SeafileDataUpdateCoordinator
from .entity import SeafileEntity

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
            [SeafileEmptyTrashButton(coordinator, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class SeafileEmptyTrashButton(SeafileEntity, ButtonEntity):
    """Button to empty the trash of a Seafile library."""

    entity_description = ButtonEntityDescription(
        key="empty_trash", translation_key="empty_trash"
    )

    def __init__(
        self, coordinator: SeafileDataUpdateCoordinator, subentry: ConfigSubentry
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, subentry, self.entity_description.key)

    @override
    async def async_press(self) -> None:
        """Permanently delete the items in the trash of the library."""
        try:
            await self.coordinator.client.clean_library_trash(self.library_id)
        except SeafilePermissionError as err:
            # Only the owner and admins of a library can empty its trash.
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="empty_trash_not_allowed"
            ) from err
        except SeafileError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="empty_trash_failed"
            ) from err
