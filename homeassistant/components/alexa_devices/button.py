"""Support for buttons."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .entity import AmazonServiceEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities for Alexa Devices."""
    coordinator = entry.runtime_data

    known_routines: set[str] = set()

    def _check_routines() -> None:
        current_routines = set(coordinator.api.routines)
        new_routines = current_routines - known_routines
        if new_routines:
            known_routines.update(new_routines)
            async_add_entities(
                AmazonRoutineButton(coordinator, routine) for routine in new_routines
            )

    _check_routines()
    entry.async_on_unload(coordinator.async_add_listener(_check_routines))


class AmazonRoutineButton(AmazonServiceEntity, ButtonEntity):
    """Button entity for Alexa routine."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AmazonDevicesCoordinator, routine: str) -> None:
        """Initialize the routine button entity."""
        self._coordinator = coordinator
        self._routine = routine
        super().__init__(
            coordinator,
            EntityDescription(key=slugify(routine), name=routine),
        )

    async def async_press(self) -> None:
        """Handle button press action."""
        await self._coordinator.api.call_routine(self._routine)
