"""Select sensor entities for LIFX integration."""

from typing import override

from lifx import ThemeLibrary

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.start import async_at_started

from .const import ATTR_THEME, DOMAIN, INFRARED_BRIGHTNESS, INFRARED_LEVELS
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


@callback
def _async_deprecate_infrared_select(
    hass: HomeAssistant, entry: LIFXConfigEntry, coordinator: LIFXUpdateCoordinator
) -> bool:
    """Return whether the deprecated infrared brightness select should be set up."""
    registry = er.async_get(hass)
    entity_id = coordinator.async_get_entity_id(Platform.SELECT, INFRARED_BRIGHTNESS)
    if entity_id is None or (select := registry.async_get(entity_id)) is None:
        return False

    @callback
    def _async_warn_or_remove(_hass: HomeAssistant) -> None:
        """Warn about the select, or drop it once it is disabled and unused."""
        if (current := registry.async_get(entity_id)) is None:
            return
        issue_id = f"deprecated_infrared_select_{entity_id}"
        used_by = automations_with_entity(hass, entity_id) + scripts_with_entity(
            hass, entity_id
        )
        if current.disabled and not used_by:
            registry.async_remove(entity_id)
            async_delete_issue(hass, DOMAIN, issue_id)
            return

        placeholders = {
            "entity_id": entity_id,
            "entity_name": current.name or current.original_name or entity_id,
            "replacement_entity_id": (
                coordinator.async_get_entity_id(Platform.NUMBER, INFRARED_BRIGHTNESS)
                or "the new infrared brightness number"
            ),
        }

        async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version="2026.11.0",
            is_fixable=True,
            data={**placeholders},
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_infrared_select",
            translation_placeholders=placeholders,
        )

    entry.async_on_unload(async_at_started(hass, _async_warn_or_remove))
    return not select.disabled


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LIFX from a config entry."""
    coordinator = entry.runtime_data

    entities: list[LIFXEntity] = []

    if coordinator.data.capabilities.has_infrared and _async_deprecate_infrared_select(
        hass, entry, coordinator
    ):
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
        await self.coordinator.async_set_infrared_brightness(
            INFRARED_LEVELS[option] * 100
        )


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
