"""Support for using ventilator with ecobee thermostats."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.fan import FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


ATTR_VENTILATOR_MIN_ON_TIME_HOME = "ventilator_min_on_time_home"
ATTR_VENTILATOR_MIN_ON_TIME_AWAY = "ventilator_min_on_time_away"

SERVICE_SET_VENTILATOR_MIN_ON_TIME_HOME = "set_ventilator_min_on_time_home"
SERVICE_SET_VENTILATOR_MIN_ON_TIME_AWAY = "set_ventilator_min_on_time_away"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat ventilator entity."""
    data = hass.data[DOMAIN]
    entities = []
    _LOGGER.debug("Adding ventilators (if present)")
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        if thermostat["settings"]["ventilatorType"] != "none":
            _LOGGER.debug("Adding 1 ventilator")
            entities.append(EcobeeVentilator(data, index))

    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_VENTILATOR_MIN_ON_TIME_HOME,
        {
            vol.Required(ATTR_VENTILATOR_MIN_ON_TIME_HOME): vol.Coerce(int),
        },
        "set_ventilator_min_on_time_home",
    )

    platform.async_register_entity_service(
        SERVICE_SET_VENTILATOR_MIN_ON_TIME_AWAY,
        {
            vol.Required(ATTR_VENTILATOR_MIN_ON_TIME_AWAY): vol.Coerce(int),
        },
        "set_ventilator_min_on_time_away",
    )


class EcobeeVentilator(FanEntity):
    """A ventilator class for an ecobee thermostat with ventilator attached."""

    def __init__(self, data, thermostat_index):
        """Initialize ecobee ventilator platform."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        self._attr_name = f'{self.thermostat["name"]} Ventilator'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=ECOBEE_MODEL_TO_NAME.get(self.thermostat["modelNumber"]),
            name=self._attr_name,
        )
        self._attr_unique_id = self.thermostat["identifier"]

    @property
    def available(self):
        """Return if device is available."""
        return self.thermostat["runtime"]["connected"]

    async def async_update(self):
        """Get the latest state from the thermostat."""
        await self.data.update()
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)

    @property
    def is_on(self):
        """Return True if the ventilator is on."""
        return "ventilator" in self.thermostat["equipmentStatus"]

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "ventilator type": self.thermostat["settings"]["ventilatorType"],
            "ventilator_min_on_time_home": self.thermostat["settings"][
                "ventilatorMinOnTimeHome"
            ],
            "ventilator_min_on_time_away": self.thermostat["settings"][
                "ventilatorMinOnTimeAway"
            ],
        }

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the ventilator 20 min manual timer."""
        self.data.ecobee.set_ventilator_timer(self.thermostat_index, True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the ventilator 20 min manual timer."""
        self.data.ecobee.set_ventilator_timer(self.thermostat_index, False)

    def set_ventilator_min_on_time_home(self, ventilator_min_on_time_home):
        """Set the minimum ventilator on time for home mode."""
        self.data.ecobee.set_ventilator_min_on_time_home(
            self.thermostat_index, ventilator_min_on_time_home
        )

    def set_ventilator_min_on_time_away(self, ventilator_min_on_time_away):
        """Set the minimum ventilator on time for away mode."""
        self.data.ecobee.set_ventilator_min_on_time_away(
            self.thermostat_index, ventilator_min_on_time_away
        )
