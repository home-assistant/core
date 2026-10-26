"""Select sensor entities for LIFX integration."""

from typing import override

from lifx import ThemeLibrary

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_THEME, INFRARED_BRIGHTNESS, INFRARED_LEVELS
from .coordinator import LIFXConfigEntry, LIFXUpdateCoordinator
from .entity import LIFXEntity

PARALLEL_UPDATES = 1

THEME_NAMES = {
    theme_name.lower(): theme_name for theme_name in ThemeLibrary.get_available_themes()
}

INFRARED_BRIGHTNESS_ENTITY = SelectEntityDescription(
    key=INFRARED_BRIGHTNESS,
    translation_key="infrared_brightness",
    entity_category=EntityCategory.CONFIG,
    options=list(INFRARED_LEVELS),
)

THEME_ENTITY = SelectEntityDescription(
    key=ATTR_THEME,
    translation_key="theme",
    entity_category=EntityCategory.CONFIG,
    options=list(THEME_NAMES),
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
        entities.append(LIFXThemeSelectEntity(coordinator, THEME_ENTITY))

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
    """Theme entity for LIFX multizone devices."""

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialise the theme selection entity."""

        super().__init__(coordinator, description)
        self._attr_current_option = None

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Update attrs from coordinator data."""
        self._attr_current_option = self.coordinator.last_used_theme

    @override
    async def async_select_option(self, option: str) -> None:
        """Paint the selected theme onto the device."""
        option = option.lower()
        await self.coordinator.async_apply_theme(THEME_NAMES[option])
        self._attr_current_option = option
        self.async_write_ha_state()
