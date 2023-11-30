"""Support for LiteJet lights."""
from __future__ import annotations

from typing import Any

from pylitejet import LiteJet, LiteJetError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEFAULT_TRANSITION, DOMAIN

ATTR_NUMBER = "number"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""

    system: LiteJet = hass.data[DOMAIN]

    entities = []
    for index in system.loads():
        name = await system.get_load_name(index)
        entities.append(LiteJetLight(config_entry, system, index, name))

    async_add_entities(entities, True)


class LiteJetLight(LightEntity):
    """Representation of a single LiteJet light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.TRANSITION
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, config_entry: ConfigEntry, system: LiteJet, index: int, name: str
    ) -> None:
        """Initialize a LiteJet light."""
        self._config_entry = config_entry
        self._lj = system
        self._index = index
        self._attr_brightness = 0
        self._attr_is_on = False
        self._attr_unique_id = f"{config_entry.entry_id}_{index}"
        self._attr_extra_state_attributes = {ATTR_NUMBER: self._index}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{config_entry.entry_id}_light_{index}")},
            name=name,
            via_device=(DOMAIN, f"{config_entry.entry_id}_mcp"),
        )

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._lj.on_load_activated(self._index, self._on_load_changed)
        self._lj.on_load_deactivated(self._index, self._on_load_changed)
        self._lj.on_connected_changed(self._on_connected_changed)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._lj.unsubscribe(self._on_load_changed)
        self._lj.unsubscribe(self._on_connected_changed)

    def _on_load_changed(self, level: int | None) -> None:
        """Handle state changes."""
        self.schedule_update_ha_state(True)

    def _on_connected_changed(self, connected: bool, reason: str) -> None:
        """Handle connected changes."""
        self.schedule_update_ha_state(True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""

        # If neither attribute is specified then the simple activate load
        # LiteJet API will use the per-light default brightness and
        # transition values programmed in the LiteJet system.
        if ATTR_BRIGHTNESS not in kwargs and ATTR_TRANSITION not in kwargs:
            try:
                await self._lj.activate_load(self._index)
            except LiteJetError as exc:
                raise HomeAssistantError() from exc
            return

        # If either attribute is specified then Home Assistant must
        # control both values.
        default_transition = self._config_entry.options.get(CONF_DEFAULT_TRANSITION, 0)
        transition = kwargs.get(ATTR_TRANSITION, default_transition)
        brightness = int(kwargs.get(ATTR_BRIGHTNESS, 255) / 255 * 99)

        try:
            await self._lj.activate_load_at(self._index, brightness, int(transition))
        except LiteJetError as exc:
            raise HomeAssistantError() from exc

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        if ATTR_TRANSITION in kwargs:
            try:
                await self._lj.activate_load_at(self._index, 0, kwargs[ATTR_TRANSITION])
            except LiteJetError as exc:
                raise HomeAssistantError() from exc
            return

        # If transition attribute is not specified then the simple
        # deactivate load LiteJet API will use the per-light default
        # transition value programmed in the LiteJet system.
        try:
            await self._lj.deactivate_load(self._index)
        except LiteJetError as exc:
            raise HomeAssistantError() from exc

    async def async_update(self) -> None:
        """Retrieve the light's brightness from the LiteJet system."""
        self._attr_available = self._lj.connected

        if not self.available:
            return

        self._attr_brightness = int(
            await self._lj.get_load_level(self._index) / 99 * 255
        )
        self._attr_is_on = self.brightness != 0
