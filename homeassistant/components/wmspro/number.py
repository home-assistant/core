"""Support for range-options of slat-cover connected with WMS WebControl pro."""

from datetime import timedelta

from wmspro.const import WMS_WebControl_pro_API_actionDescription as ACTION_DESC
from wmspro.destination import Destination

from homeassistant.components.number import NumberEntity, RestoreNumber
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
            entities.append(WebControlProSlatRange(config_entry.entry_id, d, "min"))
            entities.append(WebControlProSlatRange(config_entry.entry_id, d, "max"))
            entities.append(WebControlProSlatRotationRaw(config_entry.entry_id, d))
            if not d.hasAction(ACTION_DESC.SlatDrive):
                # Only add the numeric slat rotation entity if no cover entity exists
                entities.append(WebControlProSlatRotation(config_entry.entry_id, d))

    async_add_entities(entities)


class WebControlProSlatRange(WebControlProGenericEntity, RestoreNumber):
    """Representation of a WMS based range-option for a slat-based cover."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, config_entry_id: str, dest: Destination, name: str) -> None:
        """Initialize the entity with destination channel."""
        super().__init__(config_entry_id, dest)
        self._attr_translation_key = f"rotation-{name}"
        if self._attr_unique_id:
            self._attr_unique_id += f"-rotation-{name}"
        if name == "min":
            self._value_attr = "minValue"
            self._value_func = min
        elif name == "max":
            self._value_attr = "maxValue"
            self._value_func = max

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore previous state
        last_state = await self.async_get_last_number_data()
        if last_state is not None and last_state.native_value is not None:
            # Restore previously set/learned min/max rotation if available
            native_value = last_state.native_value
        else:
            # -75 and 75 are the most common min/max rotation values
            native_value = self._value_func(-75, 75)

        # Push restored or default value back to the hub
        await self.async_set_native_value(native_value)

    async def async_update(self) -> None:
        """Update the entity and learn current rotation."""
        await super().async_update()

        # Start with the current min/max rotation as native value
        action = self._dest.action(ACTION_DESC.SlatRotate)
        native_value = getattr(action, self._value_attr)
        if not native_value:
            native_value = self._attr_native_value
        if not native_value:
            return

        # Learn min/max rotation if different from action limits
        rotation = action["rotation"]
        if rotation and rotation not in (action.wms__minValue, action.wms__maxValue):
            native_value = self._value_func(native_value, rotation)
        await self.async_set_native_value(native_value)

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        # Use wms__ prefix to get the raw value from the hub without overwrite
        action = self._dest.action(ACTION_DESC.SlatRotate)
        return self._value_func(action.wms__minValue, 0)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        # Use wms__ prefix to get the raw value from the hub without overwrite
        action = self._dest.action(ACTION_DESC.SlatRotate)
        return self._value_func(0, action.wms__maxValue)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current min/max value."""
        # Push the new min/max rotation to the hub as custom overwrite
        action = self._dest.action(ACTION_DESC.SlatRotate)
        action[self._value_attr] = value
        if self._attr_native_value != value:
            self._attr_native_value = value
            self.async_write_ha_state()


class WebControlProSlatRotation(WebControlProGenericEntity, NumberEntity):
    """Representation of the WMS based slat-rotation for a slat-based cover."""

    _attr_translation_key = "rotation"

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

    def __init__(self, config_entry_id: str, dest: Destination) -> None:
        """Initialize the entity with destination channel."""
        super().__init__(config_entry_id, dest)
        if self._attr_unique_id:
            self._attr_unique_id += "-raw"

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
