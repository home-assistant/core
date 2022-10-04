"""Select sensor entities for LIFX integration."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, INFRARED_BRIGHTNESS, INFRARED_BRIGHTNESS_VALUES_MAP
from .coordinator import LIFXUpdateCoordinator
from .entity import LIFXEntity
from .util import lifx_features

INFRARED_BRIGHTNESS_ENTITY = SelectEntityDescription(
    key=INFRARED_BRIGHTNESS,
    name="Infrared brightness",
    entity_category=EntityCategory.CONFIG,
)

INFRARED_BRIGHTNESS_OPTIONS = list(INFRARED_BRIGHTNESS_VALUES_MAP.values())


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LIFX from a config entry."""
    coordinator: LIFXUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if lifx_features(coordinator.device)["infrared"]:
        async_add_entities(
            [
                LIFXInfraredBrightnessSelectEntity(
                    coordinator, description=INFRARED_BRIGHTNESS_ENTITY
                )
            ]
        )


class LIFXInfraredBrightnessSelectEntity(LIFXEntity, SelectEntity):
    """LIFX Nightvision infrared brightness configuration entity."""

    _attr_has_entity_name = True
    _attr_options = INFRARED_BRIGHTNESS_OPTIONS

    def __init__(
        self, coordinator: LIFXUpdateCoordinator, description: SelectEntityDescription
    ) -> None:
        """Initialise the IR brightness config entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
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
