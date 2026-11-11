"""Entities for the Input Number integration."""

from contextlib import suppress
from typing import Any, Self, override

from homeassistant.components.number import RestoreNumber
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers import collection
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_INITIAL,
    CONF_MAX,
    CONF_MIN,
    CONF_STEP,
    DOMAIN,
    InputNumberEntityStateAttribute,
)


# pylint: disable-next=home-assistant-enforce-class-module
class InputNumber(collection.CollectionEntity, RestoreNumber):
    """Representation of a slider."""

    _unrecorded_attributes = frozenset({InputNumberEntityStateAttribute.EDITABLE})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize an input number."""
        self._initial_value: float | None = config.get(CONF_INITIAL)
        self._attr_native_value = self._initial_value
        self._update_config_attributes(config)

    def _update_config_attributes(self, config: ConfigType) -> None:
        """Update attributes based on the config."""
        self._attr_icon = config.get(CONF_ICON)
        self._attr_mode = config[CONF_MODE]
        self._attr_name = config.get(CONF_NAME)
        self._attr_native_min_value = config[CONF_MIN]
        self._attr_native_max_value = config[CONF_MAX]
        self._attr_native_step = config[CONF_STEP]
        self._attr_unique_id = config[CONF_ID]
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        input_num = cls(config)
        input_num.editable = True
        return input_num

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_num = cls(config)
        input_num.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_num.editable = False
        return input_num

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            InputNumberEntityStateAttribute.INITIAL: self._initial_value,
            InputNumberEntityStateAttribute.EDITABLE: self.editable,
        }

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if self._attr_native_value is not None:
            return

        value: float | None = None
        if (number_data := await self.async_get_last_number_data()) is not None:
            value = number_data.native_value
        # Fallback for states stored without number extra data, remove in 2027.5
        elif state := await self.async_get_last_state():
            with suppress(ValueError):
                value = float(state.state)

        # Check against None because value can be 0
        if (
            value is not None
            and self.native_min_value <= value <= self.native_max_value
        ):
            self._attr_native_value = value
        else:
            self._attr_native_value = self.native_min_value

    @override
    async def async_set_native_value(self, value):
        """Set new value."""
        self._attr_native_value = float(value)
        self.async_write_ha_state()

    async def async_increment(self):
        """Increment value."""
        await self.async_set_native_value(
            min(self._attr_native_value + self.native_step, self.native_max_value)
        )

    async def async_decrement(self):
        """Decrement value."""
        await self.async_set_native_value(
            max(self._attr_native_value - self.native_step, self.native_min_value)
        )

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._update_config_attributes(config)
        if self.registry_entry:
            # Drop a display unit that no longer fits the device class or native unit
            self.async_registry_entry_updated()
        # just in case min/max values changed
        if self._attr_native_value is None:
            return
        self._attr_native_value = min(self._attr_native_value, self.native_max_value)
        self._attr_native_value = max(self._attr_native_value, self.native_min_value)
        self.async_write_ha_state()
