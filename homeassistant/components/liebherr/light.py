"""Light platform for Liebherr integration."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pyliebherrhomeapi import PresentationLightControl
from pyliebherrhomeapi.const import CONTROL_PRESENTATION_LIGHT

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LiebherrConfigEntry, LiebherrCoordinator
from .entity import LiebherrEntity

DEFAULT_MAX_BRIGHTNESS_LEVEL = 5

PARALLEL_UPDATES = 1


def _create_light_entities(
    coordinators: list[LiebherrCoordinator],
) -> list[LiebherrPresentationLight]:
    """Create light entities for the given coordinators."""
    return [
        LiebherrPresentationLight(coordinator=coordinator)
        for coordinator in coordinators
        for control in coordinator.data.controls
        if isinstance(control, PresentationLightControl)
        and control.name == CONTROL_PRESENTATION_LIGHT
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Liebherr light entities."""
    async_add_entities(
        _create_light_entities(list(entry.runtime_data.coordinators.values()))
    )

    @callback
    def _async_new_device(coordinators: list[LiebherrCoordinator]) -> None:
        """Add light entities for new devices."""
        async_add_entities(_create_light_entities(coordinators))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_new_device_{entry.entry_id}", _async_new_device
        )
    )


class LiebherrPresentationLight(LiebherrEntity, LightEntity):
    """Representation of a Liebherr presentation light."""

    _attr_translation_key = "presentation_light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
    ) -> None:
        """Initialize the presentation light entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_presentation_light"

    @property
    def _light_control(self) -> PresentationLightControl | None:
        """Get the presentation light control."""
        controls = self.coordinator.data.get_presentation_light_controls()
        return controls.get(CONTROL_PRESENTATION_LIGHT)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._light_control is not None

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        control = self._light_control
        if TYPE_CHECKING:
            assert control is not None
        if control.value is None:
            return None
        return control.value > 0

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        control = self._light_control
        if TYPE_CHECKING:
            assert control is not None
        if control.value is None or control.max is None or control.max == 0:
            return None
        return math.ceil(control.value * 255 / control.max)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        control = self._light_control
        if TYPE_CHECKING:
            assert control is not None
        max_level = control.max or DEFAULT_MAX_BRIGHTNESS_LEVEL

        if ATTR_BRIGHTNESS in kwargs:
            target = max(1, round(kwargs[ATTR_BRIGHTNESS] * max_level / 255))
        else:
            target = max_level

        await self._async_send_command(
            self.coordinator.client.set_presentation_light(
                device_id=self.coordinator.device_id,
                target=target,
            )
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_send_command(
            self.coordinator.client.set_presentation_light(
                device_id=self.coordinator.device_id,
                target=0,
            )
        )
