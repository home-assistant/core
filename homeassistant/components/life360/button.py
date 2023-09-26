"""Support for Life360 buttons."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Life360DataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Life360 buttons."""
    coordinator: Life360DataUpdateCoordinator = hass.data[DOMAIN].coordinators[
        config_entry.entry_id
    ]
    for member_id, member in coordinator.data.members.items():
        async_add_entities(
            [
                Life360UpdateLocationButton(coordinator, member.circle_id, member_id),
            ]
        )


class Life360UpdateLocationButton(
    CoordinatorEntity[Life360DataUpdateCoordinator], ButtonEntity
):
    """Represent an Life360 Update Location button."""

    _attr_has_entity_name = True
    _attr_translation_key = "update_location"

    def __init__(
        self,
        coordinator: Life360DataUpdateCoordinator,
        circle_id: str,
        member_id: str,
    ) -> None:
        """Initialize a new Life360 Update Location button."""
        super().__init__(coordinator)
        self._circle_id = circle_id
        self._member_id = member_id
        self._attr_unique_id = f"{member_id}-update-location"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, member_id)},
            name=coordinator.data.members[member_id].name,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.update_location(self._circle_id, self._member_id)
