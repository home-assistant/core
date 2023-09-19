"""Definition of the sensors of the FlexMeasures integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SCHEDULE_ENTITY, SCHEDULE_STATE, SIGNAL_UPDATE_SCHEDULE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor."""
    hass.data[DOMAIN][SCHEDULE_STATE] = {"schedule": [], "start": None}

    async_add_entities([FlexMeasuresScheduleSensor()], True)


class FlexMeasuresScheduleSensor(SensorEntity):
    """Sensor to store the schedule created by FlexMeasures."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT

    def __init__(self) -> None:
        """Sensor to store the schedule created by FlexMeasures."""
        self._attr_unique_id = SCHEDULE_ENTITY

    @property
    def name(self) -> str:
        """Sensor name."""
        return "FlexMeasures Schedule"

    @property
    def native_value(self) -> float:
        """Average power."""

        commands = self.hass.data[DOMAIN][SCHEDULE_STATE]["schedule"]
        if len(commands) == 0:
            return 0
        return sum(command["value"] for command in commands) / len(commands)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return default attributes for the FlexMeasures Schedule sensor."""
        return self.hass.data[DOMAIN][SCHEDULE_STATE]

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_SCHEDULE, self._update_callback
            )
        )

    @callback
    def _update_callback(self) -> None:
        """Update the state."""
        self.async_schedule_update_ha_state(True)
