"""Sensor entities for LIFX integration."""
from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
)
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import color_temperature_kelvin_to_mired

from .const import ATTR_ZONES, DOMAIN
from .coordinator import LIFXUpdateCoordinator
from .entity import LIFXEntity
from .util import lifx_features

MULTIZONE_ZONES_DESCRIPTION = SensorEntityDescription(
    key=ATTR_ZONES,
    name="Zones",
    icon="mdi:led-strip-variant",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LIFX from a config entry."""
    coordinator: LIFXUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if lifx_features(coordinator.device)["multizone"]:
        async_add_entities(
            [LIFXMultiZoneZonesSensorEntity(coordinator, MULTIZONE_ZONES_DESCRIPTION)]
        )


class LIFXMultiZoneZonesSensorEntity(LIFXEntity, SensorEntity):
    """LIFX MultiZone zones sensor entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise the zone count sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update attribute values."""
        self._attr_native_value = int(self.coordinator.device.zones_count)

        zones = {}
        for index, color in enumerate(self.coordinator.device.color_zones):
            hue = round(color[0] / 65535 * 360)
            saturation = round(color[1] / 65535 * 100)
            brightness = round(color[2] / 65535 * 255)
            brightness_pct = round(brightness / 255 * 100)
            color_temp = color_temperature_kelvin_to_mired(color[3])

            if saturation == 0:
                zones[f"Zone {index}"] = {
                    ATTR_COLOR_MODE: ColorMode.COLOR_TEMP,
                    ATTR_BRIGHTNESS: brightness,
                    ATTR_BRIGHTNESS_PCT: brightness_pct,
                    ATTR_COLOR_TEMP: color_temp,
                }
            else:
                zones[f"Zone {index}"] = {
                    ATTR_COLOR_MODE: ColorMode.HS,
                    ATTR_HS_COLOR: f"({hue}, {saturation})",
                    ATTR_BRIGHTNESS: brightness,
                    ATTR_BRIGHTNESS_PCT: brightness_pct,
                }

        self._attr_extra_state_attributes = zones
