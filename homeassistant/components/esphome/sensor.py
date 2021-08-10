"""Support for esphome sensors."""
from __future__ import annotations

from contextlib import suppress
from datetime import datetime
import math
from typing import cast

from aioesphomeapi import (
    SensorInfo,
    SensorState,
    SensorStateClass,
    TextSensorInfo,
    TextSensorState,
)
from aioesphomeapi.model import LastResetType
import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASSES,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt

from . import (
    EsphomeEntity,
    EsphomeEnumMapper,
    esphome_state_property,
    platform_async_setup_entry,
)

ICON_SCHEMA = vol.Schema(cv.icon)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up esphome sensors based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="sensor",
        info_type=SensorInfo,
        entity_type=EsphomeSensor,
        state_type=SensorState,
    )
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="text_sensor",
        info_type=TextSensorInfo,
        entity_type=EsphomeTextSensor,
        state_type=TextSensorState,
    )


# https://github.com/PyCQA/pylint/issues/3150 for all @esphome_state_property
# pylint: disable=invalid-overridden-method


_STATE_CLASSES: EsphomeEnumMapper[SensorStateClass, str | None] = EsphomeEnumMapper(
    {
        SensorStateClass.NONE: None,
        SensorStateClass.MEASUREMENT: STATE_CLASS_MEASUREMENT,
    }
)


class EsphomeSensor(
    EsphomeEntity[SensorInfo, SensorState], SensorEntity, RestoreEntity
):
    """A sensor implementation for esphome."""

    _old_state: float | None = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if self._static_info.last_reset_type != LastResetType.AUTO:
            return

        # Logic to restore old state for last_reset_type AUTO:
        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        if "last_reset" in last_state.attributes:
            self._attr_last_reset = dt.as_utc(
                datetime.fromisoformat(last_state.attributes["last_reset"])
            )

        with suppress(ValueError):
            self._old_state = float(last_state.state)

    @callback
    def _on_state_update(self) -> None:
        """Check last_reset when new state arrives."""
        if self._static_info.last_reset_type == LastResetType.NEVER:
            self._attr_last_reset = dt.utc_from_timestamp(0)

        if self._static_info.last_reset_type != LastResetType.AUTO:
            super()._on_state_update()
            return

        # Last reset type AUTO logic for the last_reset property
        # In this mode we automatically determine if an accumulator reset
        # has taken place.
        # We compare the last valid value (_old_state) with the new one.
        # If the value has reset to 0 or has significantly reduced we say
        # it has reset.
        new_state: float | None = None
        state = cast("str | None", self.state)
        if state is not None:
            with suppress(ValueError):
                new_state = float(state)

        did_reset = False
        if new_state is None:
            # New state is not a float - we'll detect the reset once we get valid data again
            did_reset = False
        elif self._old_state is None:
            # First measurement we ever got for this sensor, always a reset
            did_reset = True
        elif new_state == 0:
            # don't set reset if both old and new are 0
            # we would already have detected the reset on the last state
            did_reset = self._old_state != 0
        elif new_state < self._old_state:
            did_reset = True

        # Set last_reset to now if we detected a reset
        if did_reset:
            self._attr_last_reset = dt.utcnow()

        if new_state is not None:
            # Only write to old_state if the new one contains actual data
            self._old_state = new_state

        super()._on_state_update()

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        if not self._static_info.icon or self._static_info.device_class:
            return None
        return cast(str, ICON_SCHEMA(self._static_info.icon))

    @property
    def force_update(self) -> bool:
        """Return if this sensor should force a state update."""
        return self._static_info.force_update

    @esphome_state_property
    def state(self) -> str | None:
        """Return the state of the entity."""
        if math.isnan(self._state.state):
            return None
        if self._state.missing_state:
            return None
        if self.device_class == DEVICE_CLASS_TIMESTAMP:
            return dt.utc_from_timestamp(self._state.state).isoformat()
        return f"{self._state.state:.{self._static_info.accuracy_decimals}f}"

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        if not self._static_info.unit_of_measurement:
            return None
        return self._static_info.unit_of_measurement

    @property
    def device_class(self) -> str | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self._static_info.device_class not in DEVICE_CLASSES:
            return None
        return self._static_info.device_class

    @property
    def state_class(self) -> str | None:
        """Return the state class of this entity."""
        if not self._static_info.state_class:
            return None
        return _STATE_CLASSES.from_esphome(self._static_info.state_class)


class EsphomeTextSensor(EsphomeEntity[TextSensorInfo, TextSensorState], SensorEntity):
    """A text sensor implementation for ESPHome."""

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._static_info.icon

    @esphome_state_property
    def state(self) -> str | None:
        """Return the state of the entity."""
        if self._state.missing_state:
            return None
        return self._state.state
