"""Feature switches for Gree infrared climate commands."""

from typing import Any, override

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_GENERIC_OPTIONS,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_MODEL,
    DOMAIN,
    MODEL_GENERIC,
    MODEL_YAP1F,
)
from .entity import GreeIrEntity
from .state import GreeAcState

_OPTIONS = ("turbo", "light", "health", "xfan")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up option switches for supported profiles."""
    if entry.data.get(CONF_MODEL, MODEL_GENERIC) != MODEL_YAP1F and not (
        entry.data.get(CONF_MODEL, MODEL_GENERIC) == MODEL_GENERIC
        and entry.data.get(CONF_GENERIC_OPTIONS, False)
    ):
        return
    state: GreeAcState = hass.data[DOMAIN][entry.entry_id]
    entities = [GreeAcOptionSwitch(entry, state, key) for key in _OPTIONS]
    async_add_entities(entities)


class GreeAcOptionSwitch(GreeIrEntity, InfraredEmitterConsumerEntity, SwitchEntity):
    """An assumed option delegated to this entry's climate owner."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, entry: ConfigEntry, state: GreeAcState, key: str) -> None:
        """Initialize one option switch."""
        super().__init__(entry, unique_id_suffix=key)
        self._state = state
        self._key = key
        self._attr_translation_key = key
        self._infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]

    @override
    async def async_added_to_hass(self) -> None:
        """Track emitter availability and subscribe to climate state changes."""
        await super().async_added_to_hass()
        self._state.switches.append(self)
        climate = self._state.climate
        if climate is not None and climate.entity_id is not None:

            @callback
            def _handle_climate_state_change(
                event: Event[EventStateChangedData],
            ) -> None:
                self.async_write_ha_state()

            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [climate.entity_id], _handle_climate_state_change
                )
            )

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
    def is_on(self) -> bool:
        """Return the assumed switch state."""
        return getattr(self._state, self._key)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the option on and transmit a new full state."""
        await self._async_set_option(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the option off and transmit a new full state."""
        await self._async_set_option(False)

    async def _async_set_option(self, value: bool) -> None:
        """Delegate the option change to the per-entry climate owner."""
        climate = self._state.climate
        if climate is None:
            raise HomeAssistantError("Gree climate entity is not available yet")
        await climate.async_set_option(self._key, value)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Remove this entity from the shared state on unload."""
        await super().async_will_remove_from_hass()
        if self in self._state.switches:
            self._state.switches.remove(self)
