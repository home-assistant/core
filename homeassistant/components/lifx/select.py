"""Select sensor entities for LIFX integration."""
from __future__ import annotations

from aiolifx_themes.themes import ThemeLibrary

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_THEME,
    DOMAIN,
    INFRARED_BRIGHTNESS,
    INFRARED_BRIGHTNESS_VALUES_MAP,
)
from .coordinator import LIFXSensorUpdateCoordinator, LIFXUpdateCoordinator
from .entity import LIFXSensorEntity
from .util import lifx_features

THEME_NAMES = [theme_name.lower() for theme_name in ThemeLibrary().themes]

INFRARED_BRIGHTNESS_ENTITY = SelectEntityDescription(
    key=INFRARED_BRIGHTNESS,
    name="Infrared brightness",
    entity_category=EntityCategory.CONFIG,
    options=list(INFRARED_BRIGHTNESS_VALUES_MAP.values()),
)

THEME_ENTITY = SelectEntityDescription(
    key=ATTR_THEME,
    name="Theme",
    entity_category=EntityCategory.CONFIG,
    options=THEME_NAMES,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LIFX from a config entry."""
    coordinator: LIFXUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[LIFXSensorEntity] = []

    if lifx_features(coordinator.device)["infrared"]:
        entities.append(
            LIFXInfraredBrightnessSelectEntity(
                coordinator.sensor_coordinator, description=INFRARED_BRIGHTNESS_ENTITY
            )
        )

    if lifx_features(coordinator.device)["multizone"] is True:
        entities.append(
            LIFXThemeSelectEntity(
                coordinator.sensor_coordinator, description=THEME_ENTITY
            )
        )

    async_add_entities(entities)


class LIFXInfraredBrightnessSelectEntity(LIFXSensorEntity, SelectEntity):
    """LIFX Nightvision infrared brightness configuration entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LIFXSensorUpdateCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialise the IR brightness config entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.parent.serial_number}_{description.key}"
        self._attr_current_option = coordinator.current_infrared_brightness

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        self._attr_current_option = self.coordinator.current_infrared_brightness

    async def async_select_option(self, option: str) -> None:
        """Update the infrared brightness value."""
        await self.coordinator.async_set_infrared_brightness(option)


class LIFXThemeSelectEntity(LIFXSensorEntity, SelectEntity):
    """Theme entity for LIFX multizone devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LIFXSensorUpdateCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialise the theme selection entity."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.parent.serial_number}_{description.key}"
        self._attr_current_option = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from coordinator data."""
        self._attr_current_option = self.coordinator.last_used_theme

    async def async_select_option(self, option: str) -> None:
        """Paint the selected theme onto the device."""
        await self.coordinator.async_apply_theme(option.lower())
