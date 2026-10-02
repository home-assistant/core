"""Number entity for the Gree infrared countdown timer."""

from typing import override

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GreeInfraredConfigEntry
from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN
from .entity import GreeIrEntity
from .state import GreeAcState

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeInfraredConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer number entity (both profiles carry the timer bits)."""
    async_add_entities([GreeAcTimerNumber(entry, entry.runtime_data)])


class GreeAcTimerNumber(GreeIrEntity, InfraredEmitterConsumerEntity, NumberEntity):
    """Countdown timer in hours; 0 means off (the wire value is None)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_translation_key = "timer_hours"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 24.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry: ConfigEntry, state: GreeAcState) -> None:
        """Initialize the timer number entity."""
        super().__init__(entry, unique_id_suffix="timer_hours")
        self._state = state
        self._infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]

    @override
    async def async_added_to_hass(self) -> None:
        """Track emitter availability and register with the shared state."""
        await super().async_added_to_hass()
        self._state.numbers.append(self)

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
    def native_value(self) -> float:
        """Return the assumed timer value, 0 when the timer is off."""
        return self._state.timer_hours if self._state.timer_hours is not None else 0.0

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Delegate the timer change to the per-entry climate owner."""
        climate = self._state.climate
        if climate is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="climate_not_available"
            )
        await climate.async_set_timer_hours(None if value == 0 else float(value))

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Remove this entity from the shared state on unload."""
        await super().async_will_remove_from_hass()
        if self in self._state.numbers:
            self._state.numbers.remove(self)
