"""Feature switches for Gree infrared climate commands."""

from typing import Any, cast, override

from homeassistant.components.climate import HVACMode
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GreeInfraredConfigEntry
from .climate import SLEEP_BLOCKED_HVAC_MODES
from .const import (
    CONF_GENERIC_OPTIONS,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    MODEL_GENERIC,
    MODEL_YAP1F,
)
from .entity import GreeIrEntity
from .state import GreeAcState

_BASE_OPTIONS = ("turbo", "light", "health", "xfan")


PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeInfraredConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up option switches for supported profiles."""
    model = entry.data.get(CONF_MODEL, MODEL_GENERIC)
    is_yap1f = model == MODEL_YAP1F
    state = entry.runtime_data
    keys: list[str] = []
    if is_yap1f or entry.data.get(CONF_GENERIC_OPTIONS, False):
        keys.extend(_BASE_OPTIONS)
    # Sleep rides in the generic frame, so both profiles always expose it.
    keys.append("sleep")
    if is_yap1f:
        keys.extend(("ifeel", "econo", "absence"))
    async_add_entities([GreeAcOptionSwitch(entry, state, key) for key in keys])


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
        """Track emitter availability and register with the shared state."""
        await super().async_added_to_hass()
        self._state.switches.append(self)

    @property
    @override
    def available(self) -> bool:
        """Require the configured emitter and the owning climate entity."""
        climate = self._state.climate
        if not (
            self._attr_available
            and climate is not None
            and climate.entity_id is not None
            and (climate_state := self.hass.states.get(climate.entity_id)) is not None
            and climate_state.state != STATE_UNAVAILABLE
        ):
            return False
        if self._key == "sleep" and climate.hvac_mode in (
            *SLEEP_BLOCKED_HVAC_MODES,
            HVACMode.OFF,
        ):
            return False
        if self._key == "econo" and climate.hvac_mode is not HVACMode.COOL:
            return False
        if self._key == "absence" and climate.hvac_mode is not HVACMode.HEAT:
            return False
        return True

    @property
    @override
    def is_on(self) -> bool:
        """Return the assumed switch state."""
        return cast(bool, getattr(self._state, self._key))

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
