"""Support for using number with ecobee thermostats."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat number entity."""
    data = hass.data[DOMAIN]
    entities = []
    _LOGGER.debug("Adding min time ventilators numbers (if present)")
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        if thermostat["settings"]["ventilatorType"] != "none":
            _LOGGER.debug("Adding %s's ventilator min times number", thermostat["name"])
            entities.append(
                EcobeeVentilatorMinTime(
                    data,
                    index,
                    "home",
                    "ventilatorMinOnTimeHome",
                    data.ecobee.set_ventilator_min_on_time_home,
                )
            )

            entities.append(
                EcobeeVentilatorMinTime(
                    data,
                    index,
                    "away",
                    "ventilatorMinOnTimeAway",
                    data.ecobee.set_ventilator_min_on_time_away,
                )
            )

    async_add_entities(entities, True)


class EcobeeVentilatorMinTime(NumberEntity):
    """A number class, representing min time  for an ecobee thermostat with ventilator attached."""

    VENTILATOR_MIN_VALUE = 0
    VENTILATOR_MAX_VALUE = 60
    VENTILATOR_STEP = 5
    VENTILATOR_MEASUREMENT_UNIT = UnitOfTime.MINUTES
    _attr_has_entity_name = True

    def __init__(self, data, thermostat_index, mode, ecobee_setting_key, set_func):
        """Initialize ecobee ventilator platform."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        self.ecobee_setting_key = ecobee_setting_key
        self.set_func = set_func
        self._attr_name = f"Ventilator min time {mode}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=ECOBEE_MODEL_TO_NAME.get(self.thermostat["modelNumber"]),
            name=self.thermostat["name"],
        )
        self._attr_unique_id = f'{self.thermostat["identifier"]}_ventilator_{mode}'
        self._attr_native_min_value = self.VENTILATOR_MIN_VALUE
        self._attr_native_max_value = self.VENTILATOR_MAX_VALUE
        self._attr_native_step = self.VENTILATOR_STEP
        self._attr_native_value = self.thermostat["settings"][ecobee_setting_key]
        self._attr_native_unit_of_measurement = self.VENTILATOR_MEASUREMENT_UNIT

    async def async_update(self):
        """Get the latest state from the thermostat."""
        await self.data.update()
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        self._attr_native_value = self.thermostat["settings"][self.ecobee_setting_key]

    @property
    def available(self):
        """Return if device is available."""
        return self.thermostat["runtime"]["connected"]

    def set_native_value(self, value: float) -> None:
        """Set new ventilator Min On Time value."""
        self.set_func(self.thermostat_index, int(value))
