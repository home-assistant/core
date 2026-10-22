"""Entities for the Counter integration."""

from typing import Any, Self, override

from homeassistant.const import (
    CONF_ICON,
    CONF_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.helpers import collection
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_INITIAL,
    CONF_RESTORE,
    CONF_STEP,
    ENTITY_ID_FORMAT,
    CounterEntityStateAttribute,
)


class Counter(collection.CollectionEntity, RestoreEntity):
    """Representation of a counter."""

    _attr_should_poll: bool = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize a counter."""
        self._config: ConfigType = config
        self._state: int | None = config[CONF_INITIAL]

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Create counter instance from storage."""
        counter = cls(config)
        counter.editable = True
        return counter

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Create counter instance from yaml config."""
        counter = cls(config)
        counter.editable = False
        counter.entity_id = ENTITY_ID_FORMAT.format(config[CONF_ID])
        return counter

    @property
    @override
    def name(self) -> str | None:
        """Return name of the counter."""
        return self._config.get(CONF_NAME)

    @property
    @override
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    @override
    def state(self) -> int | None:
        """Return the current value of the counter."""
        return self._state

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        ret: dict[str, Any] = {
            CounterEntityStateAttribute.EDITABLE: self.editable,
            CounterEntityStateAttribute.INITIAL: self._config[CONF_INITIAL],
            CounterEntityStateAttribute.STEP: self._config[CONF_STEP],
        }
        if self._config[CONF_MINIMUM] is not None:
            ret[CounterEntityStateAttribute.MINIMUM] = self._config[CONF_MINIMUM]
        if self._config[CONF_MAXIMUM] is not None:
            ret[CounterEntityStateAttribute.MAXIMUM] = self._config[CONF_MAXIMUM]
        return ret

    @property
    @override
    def unique_id(self) -> str | None:
        """Return unique id of the entity."""
        return self._config[CONF_ID]  # type: ignore[no-any-return]

    def compute_next_state(self, state: int | None) -> int | None:
        """Keep the state within the range of min/max values."""
        if self._config[CONF_MINIMUM] is not None:
            state = max(self._config[CONF_MINIMUM], state)
        if self._config[CONF_MAXIMUM] is not None:
            state = min(self._config[CONF_MAXIMUM], state)

        return state

    @override
    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        # __init__ will set self._state to self._initial, only override
        # if needed.
        if (
            self._config[CONF_RESTORE]
            and (state := await self.async_get_last_state()) is not None
        ):
            self._state = self.compute_next_state(int(state.state))

    @callback
    def async_decrement(self) -> None:
        """Decrement the counter."""
        self._state = self.compute_next_state(self._state - self._config[CONF_STEP])
        self.async_write_ha_state()

    @callback
    def async_increment(self) -> None:
        """Increment a counter."""
        self._state = self.compute_next_state(self._state + self._config[CONF_STEP])
        self.async_write_ha_state()

    @callback
    def async_reset(self) -> None:
        """Reset a counter."""
        self._state = self.compute_next_state(self._config[CONF_INITIAL])
        self.async_write_ha_state()

    @callback
    def async_set_value(self, value: int) -> None:
        """Set counter to value."""
        if (maximum := self._config.get(CONF_MAXIMUM)) is not None and value > maximum:
            raise ValueError(
                f"Value {value} for {self.entity_id}"
                f" exceeding the maximum value of {maximum}"
            )

        if (minimum := self._config.get(CONF_MINIMUM)) is not None and value < minimum:
            raise ValueError(
                f"Value {value} for {self.entity_id}"
                f" exceeding the minimum value of {minimum}"
            )

        if (step := self._config.get(CONF_STEP)) is not None and value % step != 0:
            raise ValueError(
                f"Value {value} for {self.entity_id}"
                f" is not a multiple of the step size {step}"
            )

        self._state = value
        self.async_write_ha_state()

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Change the counter's settings WS CRUD."""
        self._config = config
        self._state = self.compute_next_state(self._state)
        self.async_write_ha_state()
