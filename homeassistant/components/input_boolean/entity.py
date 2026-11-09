"""Entities for the Input boolean integration."""

from typing import Any, Self, override

from homeassistant.const import CONF_ICON, CONF_ID, CONF_NAME, STATE_ON
from homeassistant.helpers import collection
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import CONF_INITIAL, DOMAIN, InputBooleanEntityStateAttribute


class InputBoolean(collection.CollectionEntity, ToggleEntity, RestoreEntity):
    """Representation of a boolean input."""

    _unrecorded_attributes = frozenset({InputBooleanEntityStateAttribute.EDITABLE})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize a boolean input."""
        self._config = config
        self._attr_is_on = config.get(CONF_INITIAL, False)
        self._attr_unique_id = config[CONF_ID]

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        input_bool = cls(config)
        input_bool.editable = True
        return input_bool

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_bool = cls(config)
        input_bool.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_bool.editable = False
        return input_bool

    @property
    @override
    def name(self) -> str | None:
        """Return name of the boolean input."""
        return self._config.get(CONF_NAME)

    @property
    @override
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the state attributes of the entity."""
        return {InputBooleanEntityStateAttribute.EDITABLE: self.editable}

    @override
    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        # Don't restore if we got an initial value.
        await super().async_added_to_hass()
        if self._config.get(CONF_INITIAL) is not None:
            return

        state = await self.async_get_last_state()
        self._attr_is_on = state is not None and state.state == STATE_ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False
        self.async_write_ha_state()

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._config = config
        self.async_write_ha_state()
