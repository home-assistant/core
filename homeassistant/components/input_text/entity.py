"""Entities for the Input Text integration."""

import logging
from typing import Any, Self, override

from homeassistant.components.text import TextEntity
from homeassistant.const import (
    CONF_ICON,
    CONF_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers import collection
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_INITIAL,
    CONF_MAX,
    CONF_MIN,
    CONF_PATTERN,
    DOMAIN,
    InputTextEntityStateAttribute,
)

_LOGGER = logging.getLogger(__package__)


# pylint: disable-next=home-assistant-enforce-class-module
class InputText(collection.CollectionEntity, TextEntity, RestoreEntity):
    """Represent a text box."""

    _unrecorded_attributes = frozenset({InputTextEntityStateAttribute.EDITABLE})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize a text input."""
        self._attr_native_value = config.get(CONF_INITIAL)
        self._update_config_attributes(config)

    def _update_config_attributes(self, config: ConfigType) -> None:
        """Update attributes based on the config."""
        self._attr_icon = config.get(CONF_ICON)
        self._attr_mode = config[CONF_MODE]
        self._attr_name = config.get(CONF_NAME)
        self._attr_native_min = config[CONF_MIN]
        self._attr_native_max = config[CONF_MAX]
        self._attr_pattern = config.get(CONF_PATTERN)
        self._attr_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_unique_id = config[CONF_ID]

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        input_text: Self = cls(config)
        input_text.editable = True
        return input_text

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_text: Self = cls(config)
        input_text.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_text.editable = False
        return input_text

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {InputTextEntityStateAttribute.EDITABLE: self.editable}

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if self._attr_native_value is not None:
            return

        state = await self.async_get_last_state()
        value = state.state if state else None

        # Check against None because value can be 0
        if value is not None and self.native_min <= len(value) <= self.native_max:
            self._attr_native_value = value

    @override
    async def async_set_value(self, value: str) -> None:
        """Select new value."""
        if len(value) < self.native_min or len(value) > self.native_max:
            _LOGGER.warning(
                "Invalid value: %s (length range %s - %s)",
                value,
                self.native_min,
                self.native_max,
            )
            return
        self._attr_native_value = value
        self.async_write_ha_state()

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._update_config_attributes(config)
        self.async_write_ha_state()
