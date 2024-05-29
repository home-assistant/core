"""Support for Modern Forms Fan lights."""

from __future__ import annotations

from typing import Any

from aiomodernforms.const import LIGHT_POWER_OFF, LIGHT_POWER_ON
import voluptuous as vol

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import ModernFormsDeviceEntity, modernforms_exception_handler
from .const import (
    ATTR_SLEEP_TIME,
    CLEAR_TIMER,
    DOMAIN,
    OPT_BRIGHTNESS,
    OPT_ON,
    SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
    SERVICE_SET_LIGHT_SLEEP_TIMER,
)
from .coordinator import ModernFormsDataUpdateCoordinator

BRIGHTNESS_RANGE = (1, 255)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Modern Forms platform from config entry."""

    coordinator: ModernFormsDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    # if no light unit installed no light entity
    if not coordinator.data.info.light_type:
        return

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_LIGHT_SLEEP_TIMER,
        {
            vol.Required(ATTR_SLEEP_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=1440)
            ),
        },
        "async_set_light_sleep_timer",
    )

    platform.async_register_entity_service(
        SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
        {},
        "async_clear_light_sleep_timer",
    )

    async_add_entities(
        [
            ModernFormsLightEntity(
                entry_id=config_entry.entry_id, coordinator=coordinator
            )
        ]
    )


class ModernFormsLightEntity(ModernFormsDeviceEntity, LightEntity):
    """Defines a Modern Forms light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_translation_key = "light"

    def __init__(
        self, entry_id: str, coordinator: ModernFormsDataUpdateCoordinator
    ) -> None:
        """Initialize Modern Forms light."""
        super().__init__(
            entry_id=entry_id,
            coordinator=coordinator,
        )
        self._attr_unique_id = f"{self.coordinator.data.info.mac_address}"

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        return round(
            percentage_to_ranged_value(
                BRIGHTNESS_RANGE, self.coordinator.data.state.light_brightness
            )
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        return bool(self.coordinator.data.state.light_on)

    @modernforms_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.modern_forms.light(on=LIGHT_POWER_OFF)

    @modernforms_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        data = {OPT_ON: LIGHT_POWER_ON}

        if ATTR_BRIGHTNESS in kwargs:
            data[OPT_BRIGHTNESS] = ranged_value_to_percentage(
                BRIGHTNESS_RANGE, kwargs[ATTR_BRIGHTNESS]
            )

        await self.coordinator.modern_forms.light(**data)

    @modernforms_exception_handler
    async def async_set_light_sleep_timer(
        self,
        sleep_time: int,
    ) -> None:
        """Set a Modern Forms light sleep timer."""
        await self.coordinator.modern_forms.light(sleep=sleep_time * 60)

    @modernforms_exception_handler
    async def async_clear_light_sleep_timer(
        self,
    ) -> None:
        """Clear a Modern Forms light sleep timer."""
        await self.coordinator.modern_forms.light(sleep=CLEAR_TIMER)
