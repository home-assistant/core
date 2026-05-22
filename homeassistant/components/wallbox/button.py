"""Home Assistant component for accessing the Wallbox Portal API. The button component creates a button entity."""

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CHARGER_DATA_KEY,
    CHARGER_RESUME_SCHEDULE_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
)
from .coordinator import WallboxConfigEntry, WallboxCoordinator
from .entity import WallboxEntity

BUTTON_TYPES: dict[str, ButtonEntityDescription] = {
    CHARGER_RESUME_SCHEDULE_KEY: ButtonEntityDescription(
        key=CHARGER_RESUME_SCHEDULE_KEY,
        translation_key=CHARGER_RESUME_SCHEDULE_KEY,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WallboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create wallbox button entities in HASS."""
    coordinator: WallboxCoordinator = entry.runtime_data
    async_add_entities(
        [WallboxButton(coordinator, BUTTON_TYPES[CHARGER_RESUME_SCHEDULE_KEY])]
    )


# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class WallboxButton(WallboxEntity, ButtonEntity):
    """Representation of the Wallbox portal."""

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize a Wallbox button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{description.key}-"
            f"{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"
        )

    async def async_press(self) -> None:
        """Resume schedule and EcoSmart mode after a manual stop."""
        await self.coordinator.async_resume_schedule()
