"""Support for Salda Smarty XP/XV Ventilation Unit Binary Sensors."""

from __future__ import annotations

import logging

from pysmarty2 import Smarty

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SIGNAL_UPDATE_SMARTY, SmartyConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarty Binary Sensor Platform."""

    smarty = entry.runtime_data
    entry_id = entry.entry_id
    sensors = [
        AlarmSensor(entry.title, smarty, entry_id),
        WarningSensor(entry.title, smarty, entry_id),
        BoostSensor(entry.title, smarty, entry_id),
    ]

    async_add_entities(sensors, True)


class SmartyBinarySensor(BinarySensorEntity):
    """Representation of a Smarty Binary Sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        device_class: BinarySensorDeviceClass | None,
        smarty: Smarty,
    ) -> None:
        """Initialize the entity."""
        self._attr_name = name
        self._attr_device_class = device_class
        self._smarty = smarty

    async def async_added_to_hass(self) -> None:
        """Call to update."""
        async_dispatcher_connect(self.hass, SIGNAL_UPDATE_SMARTY, self._update_callback)

    @callback
    def _update_callback(self) -> None:
        """Call update method."""
        self.async_schedule_update_ha_state(True)


class BoostSensor(SmartyBinarySensor):
    """Boost State Binary Sensor."""

    def __init__(self, name: str, smarty: Smarty, entry_id: str) -> None:
        """Alarm Sensor Init."""
        super().__init__(name=f"{name} Boost State", device_class=None, smarty=smarty)
        self._attr_unique_id = f"{entry_id}_boost"

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug("Updating sensor %s", self._attr_name)
        self._attr_is_on = self._smarty.boost


class AlarmSensor(SmartyBinarySensor):
    """Alarm Binary Sensor."""

    def __init__(self, name: str, smarty: Smarty, entry_id: str) -> None:
        """Alarm Sensor Init."""
        super().__init__(
            name=f"{name} Alarm",
            device_class=BinarySensorDeviceClass.PROBLEM,
            smarty=smarty,
        )
        self._attr_unique_id = f"{entry_id}_alarm"

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug("Updating sensor %s", self._attr_name)
        self._attr_is_on = self._smarty.alarm


class WarningSensor(SmartyBinarySensor):
    """Warning Sensor."""

    def __init__(self, name: str, smarty: Smarty, entry_id: str) -> None:
        """Warning Sensor Init."""
        super().__init__(
            name=f"{name} Warning",
            device_class=BinarySensorDeviceClass.PROBLEM,
            smarty=smarty,
        )
        self._attr_unique_id = f"{entry_id}_warning"

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug("Updating sensor %s", self._attr_name)
        self._attr_is_on = self._smarty.warning
