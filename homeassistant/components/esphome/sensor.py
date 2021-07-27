"""Support for esphome sensors."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, DecimalException
import logging
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

from homeassistant.components.esphome.entry_data import RuntimeEntryData
from homeassistant.components.sensor import (
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASSES,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt

from . import (
    EsphomeEntity,
    EsphomeEnumMapper,
    esphome_state_property,
    platform_async_setup_entry,
)

ICON_SCHEMA = vol.Schema(cv.icon)

_LOGGER = logging.getLogger(__name__)


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


class EsphomeSensor(EsphomeEntity[SensorInfo, SensorState], SensorEntity):
    """A sensor implementation for esphome."""

    def __init__(
        self, entry_data: RuntimeEntryData, component_key: str, key: int
    ) -> None:
        """Initialize."""
        super().__init__(entry_data, component_key, key)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if self._static_info.last_reset_type is LastResetType.NEVER:
            self._attr_last_reset = datetime.min
        elif self._static_info.last_reset_type is LastResetType.AUTO:

            @callback
            def check_last_state(event: Event) -> None:
                """Check the states to see if last_reset should be set to now."""
                old_state = event.data.get("old_state")
                new_state = event.data.get("new_state")
                _LOGGER.warning(f"Checking states {old_state} -> {new_state}")

                reset = old_state is None
                old = None
                new = None
                try:
                    assert new_state is not None
                    new = Decimal(new_state.state)
                except DecimalException:
                    return

                _LOGGER.error(f"Reset? {reset}")

                if not reset:
                    assert old_state is not None
                    try:
                        old = Decimal(old_state.state)
                    except DecimalException as err:
                        _LOGGER.warning(
                            "Invalid old state (%s > %s): %s",
                            old_state.state,
                            new,
                            err,
                        )
                if old == 0 and new == 0:
                    return

                if not reset:
                    _LOGGER.warning(
                        f"new == 0? {new == 0}; old is None? {True if old is None else f'False; new < (old / 2)? {new < (old / 2)}'}"
                    )
                    reset = new == 0 or (old is not None and new < (old / 2))

                if reset:
                    _LOGGER.warning("Setting last_reset to now")
                    self._attr_last_reset = datetime.now()
                    self.async_write_ha_state()

            async_track_state_change_event(
                self.hass, [self.entity_id], check_last_state
            )

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
