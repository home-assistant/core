"""Light platform for fressnapf_tracker."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FressnapfTrackerConfigEntry
from .const import DOMAIN
from .entity import FressnapfTrackerEntity

PARALLEL_UPDATES = 1

LIGHT_ENTITY_DESCRIPTION = LightEntityDescription(
    translation_key="led",
    entity_category=EntityCategory.CONFIG,
    key="led_brightness_value",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FressnapfTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fressnapf Tracker lights."""

    async_add_entities(
        FressnapfTrackerLight(coordinator, LIGHT_ENTITY_DESCRIPTION)
        for coordinator in entry.runtime_data
        if coordinator.data.led_activatable is not None
        and coordinator.data.led_activatable.has_led
        and coordinator.data.tracker_settings.features.flash_light
    )


class FressnapfTrackerLight(FressnapfTrackerEntity, LightEntity):
    """Fressnapf Tracker light."""

    _attr_color_mode: ColorMode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        if TYPE_CHECKING:
            # The entity is not created if led_brightness_value is None
            assert self.coordinator.data.led_brightness_value is not None
        return int(round((self.coordinator.data.led_brightness_value / 100) * 255))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        self.raise_if_not_activatable()
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        brightness = int((brightness / 255) * 100)
        await self.coordinator.client.set_led_brightness(brightness)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self.coordinator.client.set_led_brightness(0)
        await self.coordinator.async_request_refresh()

    def raise_if_not_activatable(self) -> None:
        """Raise error with reasoning if light is not activatable."""
        if TYPE_CHECKING:
            # The entity is not created if led_activatable is None
            assert self.coordinator.data.led_activatable is not None
        error_type: str | None = None
        if not self.coordinator.data.led_activatable.seen_recently:
            error_type = "not_seen_recently"
        elif not self.coordinator.data.led_activatable.not_charging:
            error_type = "charging"
        elif not self.coordinator.data.led_activatable.nonempty_battery:
            error_type = "low_battery"
        if error_type is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=error_type,
            )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        if self.coordinator.data.led_brightness_value is not None:
            return self.coordinator.data.led_brightness_value > 0
        return False
