"""Select sensor entities for LIFX integration."""

from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import INFRARED_BRIGHTNESS, INFRARED_LEVELS
from .coordinator import LIFXConfigEntry, LIFXUpdateCoordinator
from .entity import LIFXEntity
from .util import THEME_OPTIONS, THEME_SELECT_OPTIONS

PARALLEL_UPDATES = 1

INFRARED_BRIGHTNESS_ENTITY = SelectEntityDescription(
    key=INFRARED_BRIGHTNESS,
    translation_key="infrared_brightness",
    entity_category=EntityCategory.CONFIG,
    options=list(INFRARED_LEVELS),
)

THEME_ENTITY = SelectEntityDescription(
    key="theme",
    translation_key="theme",
    entity_category=EntityCategory.CONFIG,
    options=THEME_SELECT_OPTIONS,
)

MOOD_ENTITY = SelectEntityDescription(
    key="mood",
    translation_key="mood",
    entity_category=EntityCategory.CONFIG,
    options=THEME_OPTIONS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LIFX from a config entry."""
    coordinator = entry.runtime_data

    entities: list[LIFXEntity] = []

    if coordinator.data.capabilities.has_infrared:
        entities.append(
            LIFXInfraredBrightnessSelectEntity(coordinator, INFRARED_BRIGHTNESS_ENTITY)
        )

    if (
        coordinator.data.capabilities.has_multizone
        or coordinator.data.capabilities.has_matrix
    ):
        entities.extend(
            (
                LIFXThemeSelectEntity(coordinator, THEME_ENTITY),
                LIFXMoodSelectEntity(coordinator, MOOD_ENTITY),
            )
        )

    async_add_entities(entities)


class LIFXInfraredBrightnessSelectEntity(LIFXEntity, SelectEntity):
    """LIFX Nightvision infrared brightness configuration entity."""

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialise the IR brightness config entity."""
        super().__init__(coordinator, description)
        self._attr_current_option = coordinator.current_infrared_brightness

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        self._attr_current_option = self.coordinator.current_infrared_brightness

    @override
    async def async_select_option(self, option: str) -> None:
        """Update the infrared brightness value."""
        await self.coordinator.async_set_infrared_brightness(option)


class LIFXThemeSelectEntity(LIFXEntity, SelectEntity):
    """Theme entity for LIFX multizone and matrix devices."""

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialise the theme selection entity."""
        super().__init__(coordinator, description)
        self._attr_current_option = coordinator.current_theme

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Show the theme the library says the light still shows."""
        self._attr_current_option = self.coordinator.current_theme

    @override
    async def async_select_option(self, option: str) -> None:
        """Paint the selected theme onto the device."""
        await self.coordinator.async_apply_theme(option)


class LIFXMoodSelectEntity(LIFXEntity, SelectEntity):
    """Mood entity for LIFX multizone and matrix devices."""

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialise the Mood selection entity."""
        super().__init__(coordinator, description)
        self._attr_current_option = coordinator.current_mood

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Show the Mood the library says the light still shows."""
        self._attr_current_option = self.coordinator.current_mood

    @override
    async def async_select_option(self, option: str) -> None:
        """Apply the selected Mood to the device."""
        await self.coordinator.async_apply_mood(option)
