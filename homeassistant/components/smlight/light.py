"""Light platform for SLZB-Ultima Ambilight."""

from dataclasses import dataclass
import logging
from typing import Any

from pysmlight.const import AMBI_EFFECT_LIST, AmbiEffect, Pages
from pysmlight.models import AmbilightPayload

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SmConfigEntry, SmDataUpdateCoordinator
from .entity import SmEntity

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class SmLightEntityDescription(LightEntityDescription):
    """Class describing Smlight light entities."""

    effect_list: list[str]


AMBILIGHT = SmLightEntityDescription(
    key="ambilight",
    translation_key="ambilight",
    icon="mdi:led-strip",
    effect_list=AMBI_EFFECT_LIST,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize light for SLZB-Ultima device."""
    coordinator = entry.runtime_data.data

    if coordinator.data.info.has_peripherals:
        async_add_entities([SmLightEntity(coordinator, AMBILIGHT)])


class SmLightEntity(SmEntity, LightEntity):
    """Representation of light entity for SLZB-Ultima Ambilight."""

    coordinator: SmDataUpdateCoordinator
    entity_description: SmLightEntityDescription
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmLightEntityDescription,
    ) -> None:
        """Initialize light entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
        self._attr_effect_list = description.effect_list

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if ambi := self.coordinator.data.sensors.ambilight:
            self._attr_is_on = ambi.ultLedMode not in (None, AmbiEffect.WSULT_OFF)
            self._attr_brightness = ambi.ultLedBri
            self._attr_effect = self._effect_from_mode(ambi.ultLedMode)
            self._attr_rgb_color = self._parse_rgb_color(ambi.ultLedColor)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Register SSE page callback when entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.client.sse.register_page_cb(
                Pages.API2_PAGE_AMBILIGHT, self._handle_ambilight_changes
            )
        )

    @callback
    def _handle_ambilight_changes(self, changes: dict) -> None:
        """Handle ambilight SSE event."""
        self.coordinator.update_ambilight(changes)

    def _effect_from_mode(self, mode: AmbiEffect | None) -> str | None:
        """Return the effect name for a given AmbiEffect mode."""
        if mode is None:
            return None
        try:
            return self.entity_description.effect_list[int(mode)]
        except IndexError, ValueError:
            return None

    def _parse_rgb_color(self, color: str | None) -> tuple[int, int, int] | None:
        """Parse a hex color string into an RGB tuple."""
        try:
            if color and color.startswith("#"):
                return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
        except ValueError:
            pass
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Format kwargs into the specific schema for SLZB-OS and set."""
        payload = AmbilightPayload()

        if ATTR_EFFECT in kwargs:
            effect_name: str = kwargs[ATTR_EFFECT]
            try:
                idx = self.entity_description.effect_list.index(effect_name)
            except ValueError:
                _LOGGER.warning("Unknown effect: %s", effect_name)
                return
            payload.ultLedMode = AmbiEffect(idx)
        elif not self.is_on:
            payload.ultLedMode = AmbiEffect.WSULT_SOLID

        if ATTR_BRIGHTNESS in kwargs:
            payload.ultLedBri = kwargs[ATTR_BRIGHTNESS]
        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            payload.ultLedColor = f"#{r:02x}{g:02x}{b:02x}"

        if payload == AmbilightPayload():
            return

        await self.coordinator.async_execute_command(
            self.coordinator.client.actions.ambilight, payload
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Ambilight off using effect OFF."""
        await self.coordinator.async_execute_command(
            self.coordinator.client.actions.ambilight,
            AmbilightPayload(ultLedMode=AmbiEffect.WSULT_OFF),
        )
