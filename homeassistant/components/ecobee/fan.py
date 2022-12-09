"""Support for using ventilator with ecobee thermostats."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.fan import FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

SCAN_INTERVAL = timedelta(minutes=3)

ATTR_VENTILATOR_MIN_ON_TIME_HOME = "ventilator_min_on_time_home"
ATTR_VENTILATOR_MIN_ON_TIME_AWAY = "ventilator_min_on_time_away"
ATTR_IS_VENTILATOR_TIMER_ON = "is_ventilator_timer_on"

SERVICE_SET_VENTILATOR_MIN_ON_TIME_HOME = "set_ventilator_min_on_time_home"
SERVICE_SET_VENTILATOR_MIN_ON_TIME_AWAY = "set_ventilator_min_on_time_away"
SERVICE_SET_VENTILATOR_TIMER = "set_ventilator_timer"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat ventilator entity."""
    data = hass.data[DOMAIN]
    entities = []
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        if thermostat["settings"]["ventilatorType"] != "none":
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

    platform.async_register_entity_service(
        SERVICE_SET_VENTILATOR_TIMER,
        {
            vol.Required(ATTR_IS_VENTILATOR_TIMER_ON): cv.boolean,
        },
        "set_ventilator_timer",
    )


class EcobeeVentilator(FanEntity):
    """A ventilator class for an ecobee thermostat with ventilator attached."""

    def __init__(self, data, thermostat_index):
        """Initialize ecobee ventilator platform."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        self._name = "Ventilator"

        self.update_without_throttle = False

    @property
    def name(self):
        """Return the name of the ventilator."""
        return self._name

    @property
    def unique_id(self):
        """Return unique_id for ventilator."""
        return f"{self.thermostat['identifier']}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the ecobee ventilator."""
        model: str | None
        try:
            model = f"{ECOBEE_MODEL_TO_NAME[self.thermostat['modelNumber']]} Thermostat"
        except KeyError:
            # Ecobee model is not in our list
            model = None

        return DeviceInfo(
            identifiers={(DOMAIN, self.thermostat["identifier"])},
            manufacturer=MANUFACTURER,
            model=model,
            name=self.name,
        )

    @property
    def available(self):
        """Return if device is available."""
        return self.thermostat["runtime"]["connected"]

    async def async_update(self):
        """Get the latest state from the thermostat."""
        if self.update_without_throttle:
            await self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
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
            "is_ventilator_timer_on": self.thermostat["settings"][
                "isVentilatorTimerOn"
            ],
        }

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the ventilator 20 min manual timer."""
        self.set_ventilator_timer(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the ventilator 20 min manual timer."""
        self.set_ventilator_timer(False)

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

    def set_ventilator_timer(self, is_ventilator_timer_on):
        """Set the ventilator timer.

        If set to true, the ventilator_off_date_time is set to now() + 20 minutes,
        ventilator will start running and stop after 20 minutes.
        If set to false, the ventilator_off_date_time is set to it's default value,
        ventilator will stop.
        """
        self.data.ecobee.set_ventilator_timer(
            self.thermostat_index, is_ventilator_timer_on
        )
