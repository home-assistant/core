"""Support for Litter-Robot images."""

from typing import override

from pylitterbot import Pet

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import LitterRobotEntity

PARALLEL_UPDATES = 0

PET_IMAGE = ImageEntityDescription(key="image", name=None)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot image platform."""
    coordinator = entry.runtime_data
    known_pets: set[str] = set()

    def _check_pets() -> None:
        # A pet only gets an image entity once it has a profile image.
        new_pets = [
            pet
            for pet in coordinator.account.pets
            if pet.image_url and pet.id not in known_pets
        ]
        if new_pets:
            known_pets.update(pet.id for pet in new_pets)
            async_add_entities(
                PetImageEntity(pet=pet, coordinator=coordinator, description=PET_IMAGE)
                for pet in new_pets
            )

    _check_pets()
    entry.async_on_unload(coordinator.async_add_listener(_check_pets))


class PetImageEntity(LitterRobotEntity[Pet], ImageEntity):
    """Litter-Robot pet image entity."""

    def __init__(
        self,
        pet: Pet,
        coordinator: LitterRobotDataUpdateCoordinator,
        description: ImageEntityDescription,
    ) -> None:
        """Initialize a pet image entity."""
        super().__init__(pet, coordinator, description)
        ImageEntity.__init__(self, coordinator.hass)
        self._update_image_attributes()

    def _update_image_attributes(self) -> None:
        """Reset the cached image when the pet's image url changes."""
        if (url := self.robot.image_url) != self._attr_image_url:
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_image_attributes()
        super()._handle_coordinator_update()
