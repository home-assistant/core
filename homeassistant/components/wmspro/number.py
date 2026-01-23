"""Support for range-options of slat-cover connected with WMS WebControl pro."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from wmspro.const import WMS_WebControl_pro_API_actionDescription as ACTION_DESC
from wmspro.destination import Destination

from homeassistant.components.number import NumberEntity, RestoreNumber
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebControlProConfigEntry
from .const import DOMAIN
from .entity import WebControlProGenericEntity

SCAN_INTERVAL = timedelta(seconds=15)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WMS based covers from a config entry."""
    hub = config_entry.runtime_data

    entities: list[WebControlProGenericEntity] = []
    for d in hub.dests.values():
        if d.hasAction(ACTION_DESC.SlatDrive) and d.hasAction(ACTION_DESC.SlatRotate):
            entities.append(WebControlProSlatRange(config_entry.entry_id, d, min))
            entities.append(WebControlProSlatRange(config_entry.entry_id, d, max))
        if d.hasAction(ACTION_DESC.SlatRotate):
            entities.append(WebControlProSlatRotation(config_entry.entry_id, d))

    async_add_entities(entities)


class WebControlProSlatRange(WebControlProGenericEntity, RestoreNumber):
    """Representation of a WMS based range-option for a slat-based cover."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, config_entry_id: str, dest: Destination, func: Callable) -> None:
        """Initialize the entity with destination channel."""
        super().__init__(config_entry_id, dest)
        self._value_func = func
        self._attr_translation_key = f"rotation-{func.__name__}"
        if self._attr_unique_id:
            self._attr_unique_id += f"-rotation-{func.__name__}"
        if self._value_func == min:
            self._attr_icon = "mdi:rotate-left"
        elif self._value_func == max:
            self._attr_icon = "mdi:rotate-right"

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore previous state
        last_state = await self.async_get_last_number_data()
        if last_state is not None and last_state.native_value is not None:
            # Restore previously set/learned min/max rotation if available
            self._attr_native_value = last_state.native_value
        else:
            # -75 and 75 are the most common min/max rotation values
            self._attr_native_value = self._value_func(-75, 75)

        # Register entity in hass data for access by cover entity
        if self._attr_unique_id:
            self.hass.data[DOMAIN][self._attr_unique_id] = self

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity which will be removed."""
        await super().async_will_remove_from_hass()

        # Remove entity from hass data
        if self._attr_unique_id and self._attr_unique_id in self.hass.data[DOMAIN]:
            del self.hass.data[DOMAIN][self._attr_unique_id]

    async def async_update(self) -> None:
        """Update the entity and learn current rotation."""
        await super().async_update()

        # Get current rotation and update value
        action = self._dest.action(ACTION_DESC.SlatRotate)
        if action is not None:
            rotation = action["rotation"]
            if rotation is not None:
                self._attr_native_value = self._value_func(
                    self._attr_native_value, rotation
                )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        return self._value_func(action.minValue, 0)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        return self._value_func(0, action.maxValue)

    def set_native_value(self, value: float) -> None:
        """Update the current min/max value."""
        self._attr_native_value = value


class WebControlProSlatRotation(WebControlProGenericEntity, NumberEntity):
    """Representation of a WMS based slat-rotation for a slat-based cover."""

    _attr_icon = "mdi:rotate-360"
    _attr_translation_key = "rotation"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, config_entry_id: str, dest: Destination) -> None:
        """Initialize the entity with destination channel."""
        super().__init__(config_entry_id, dest)
        if self._attr_unique_id:
            self._attr_unique_id += "-rotation"

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        return action.minValue

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        return action.maxValue

    @property
    def native_value(self) -> float:
        """Return the current value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        return action["rotation"]

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        await action(rotation=value)
