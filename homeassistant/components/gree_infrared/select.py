"""Select entities for Gree infrared climate commands."""

from typing import override

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GreeInfraredConfigEntry
from .climate import (
    DISPLAY_TEMP_OPTIONS,
    FRESH_AIR_OPTIONS,
    HORIZONTAL_POSITION_OPTIONS,
    VANE_AUTO,
    VANE_OPTIONS,
)
from .const import CONF_INFRARED_EMITTER_ENTITY_ID, MODEL_GENERIC, MODEL_YAP1F
from .entity import GreeIrEntity
from .state import GreeAcState

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeInfraredConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities for supported profiles."""
    model = entry.data.get(CONF_MODEL, MODEL_GENERIC)
    keys = ["fresh_air"]
    if model == MODEL_YAP1F:
        keys.extend(
            ("swing_v_position", "swing_h_position", "display_temp", "fahrenheit")
        )
    state = entry.runtime_data
    async_add_entities([GreeAcOptionSelect(entry, state, key) for key in keys])


class GreeAcOptionSelect(GreeIrEntity, InfraredEmitterConsumerEntity, SelectEntity):
    """An assumed select delegated to this entry's climate owner."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, entry: ConfigEntry, state: GreeAcState, key: str) -> None:
        """Initialize one option select."""
        super().__init__(entry, unique_id_suffix=key)
        self._state = state
        self._key = key
        self._attr_translation_key = key
        self._attr_options = {
            "fresh_air": FRESH_AIR_OPTIONS,
            "swing_v_position": VANE_OPTIONS,
            "swing_h_position": HORIZONTAL_POSITION_OPTIONS,
            "display_temp": DISPLAY_TEMP_OPTIONS,
            "fahrenheit": ["celsius", "fahrenheit"],
        }[key]
        self._infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]

    @override
    async def async_added_to_hass(self) -> None:
        """Track emitter availability and register with the shared state."""
        await super().async_added_to_hass()
        self._state.selects.append(self)

    @property
    @override
    def available(self) -> bool:
        """Require the configured emitter and the owning climate entity."""
        climate = self._state.climate
        return (
            self._attr_available
            and climate is not None
            and climate.entity_id is not None
            and (climate_state := self.hass.states.get(climate.entity_id)) is not None
            and climate_state.state != STATE_UNAVAILABLE
        )

    @property
    @override
    def current_option(self) -> str | None:
        if self._key == "fresh_air":
            return FRESH_AIR_OPTIONS[self._state.fresh_air]
        if self._key == "swing_v_position":
            if self._state.swing_v_position is None:
                return VANE_AUTO
            return str(self._state.swing_v_position)
        if self._key == "swing_h_position":
            return HORIZONTAL_POSITION_OPTIONS[self._state.swing_h_position]
        if self._key == "display_temp":
            return DISPLAY_TEMP_OPTIONS[self._state.display_temp]
        return "fahrenheit" if self._state.fahrenheit else "celsius"

    @override
    async def async_select_option(self, option: str) -> None:
        """Delegate the select change to the per-entry climate owner."""
        climate = self._state.climate
        if climate is None:
            raise HomeAssistantError("Gree climate entity is not available yet")
        if self._key == "fresh_air":
            await climate.async_set_fresh_air(option)
        elif self._key == "swing_v_position":
            if option == VANE_AUTO:
                await climate.async_set_swing_v_position(None)
            else:
                await climate.async_set_swing_v_position(int(option))
        elif self._key == "swing_h_position":
            await climate.async_set_swing_h_position(
                HORIZONTAL_POSITION_OPTIONS.index(option)
            )
        elif self._key == "display_temp":
            await climate.async_set_display_temp(DISPLAY_TEMP_OPTIONS.index(option))
        else:
            await climate.async_set_fahrenheit(option == "fahrenheit")

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Remove this entity from the shared state on unload."""
        await super().async_will_remove_from_hass()
        if self in self._state.selects:
            self._state.selects.remove(self)
