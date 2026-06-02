"""Support for range-options of slat-cover connected with WMS WebControl pro."""

from collections.abc import Callable
from datetime import timedelta

from wmspro.const import WMS_WebControl_pro_API_actionDescription as ACTION_DESC

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebControlProConfigEntry
from .entity import WebControlProGenericEntity

SCAN_INTERVAL = timedelta(seconds=15)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WMS based slat rotation number entities from a config entry."""
    hub = config_entry.runtime_data

    entities: list[WebControlProGenericEntity] = []
    for d in hub.dests.values():
        if d.hasAction(ACTION_DESC.SlatRotate):
            entities.append(WebControlProSlatRangeMin(config_entry.entry_id, d))
            entities.append(WebControlProSlatRangeMax(config_entry.entry_id, d))
            entities.append(WebControlProSlatRotationRaw(config_entry.entry_id, d))
            if not d.hasAction(ACTION_DESC.SlatDrive):
                # Only add the numeric slat rotation entity if no cover entity exists
                entities.append(WebControlProSlatRotation(config_entry.entry_id, d))

    async_add_entities(entities)


class WebControlProSlatRange(WebControlProGenericEntity, NumberEntity):
    """Representation of a WMS based range-option for a slat-based cover."""

    _attr_entity_category = EntityCategory.CONFIG

    _value_func: Callable
    _value_name: str

    async def async_update(self) -> None:
        """Update the entity and learn current rotation."""
        await super().async_update()

        # Learn min/max rotation if different from action limits
        action = self._dest.action(ACTION_DESC.SlatRotate)
        rotation = action["rotation"]
        if rotation and action.wms__minValue < rotation < action.wms__maxValue:
            await self.async_set_native_value(
                self._value_func(self.native_value, rotation)
            )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        # Use wms__ prefix to get the raw value from the hub without overwrite
        return self._value_func(action.wms__minValue, 0)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        # Use wms__ prefix to get the raw value from the hub without overwrite
        return self._value_func(0, action.wms__maxValue)

    @property
    def native_value(self) -> float:
        """Return the current min/max value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        # Pull the current min/max rotation from the custom overwrite if set
        value = action[self._value_name]
        # -75 and 75 are community-provided sane defaults for various devices
        if value is None:
            value = self._value_func(-75, 75)
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Update the current min/max value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        # Push the new min/max rotation to the hub as custom overwrite
        action[self._value_name] = value


class WebControlProSlatRangeMin(WebControlProSlatRange):
    """Representation of the minimum rotation range-option for a slat-based cover."""

    _attr_translation_key = "rotation-min"

    _value_name = "minValue"
    _value_func = min


class WebControlProSlatRangeMax(WebControlProSlatRange):
    """Representation of the maximum rotation range-option for a slat-based cover."""

    _attr_translation_key = "rotation-max"

    _value_name = "maxValue"
    _value_func = max


class WebControlProSlatRotation(WebControlProGenericEntity, NumberEntity):
    """Representation of the WMS based slat-rotation for a slat-based cover."""

    _attr_translation_key = "rotation"

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
    def native_value(self) -> float | None:
        """Return the current value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        rotation = action["rotation"]
        if rotation is None:
            return None
        return rotation

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        await action(rotation=value)


class WebControlProSlatRotationRaw(WebControlProSlatRotation):
    """Representation of the WMS based raw slat-rotation for a slat-based cover."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "rotation-raw"

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        return action.wms__minValue

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        return action.wms__maxValue
