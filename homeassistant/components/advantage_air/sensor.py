"""Sensor platform for Advantage Air integration."""
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import ADVANTAGE_AIR_STATE_OPEN, DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirEntity

ADVANTAGE_AIR_SET_COUNTDOWN_VALUE = "minutes"
ADVANTAGE_AIR_SET_COUNTDOWN_UNIT = "min"
ADVANTAGE_AIR_SERVICE_SET_TIME_TO = "set_time_to"

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir sensor platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
    for ac_key, ac_device in instance["coordinator"].data["aircons"].items():
        entities.append(AdvantageAirTimeTo(instance, ac_key, "On"))
        entities.append(AdvantageAirTimeTo(instance, ac_key, "Off"))
        for zone_key, zone in ac_device["zones"].items():
            # Only show damper sensors when zone is in temperature control
            if zone["type"] != 0:
                entities.append(AdvantageAirZoneVent(instance, ac_key, zone_key))
            # Only show wireless signal strength sensors when using wireless sensors
            if zone["rssi"] > 0:
                entities.append(AdvantageAirZoneSignal(instance, ac_key, zone_key))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {vol.Required("minutes"): cv.positive_int},
        "set_time_to",
    )


class AdvantageAirTimeTo(AdvantageAirEntity, SensorEntity):
    """Representation of Advantage Air timer control."""

    _attr_unit_of_measurement = ADVANTAGE_AIR_SET_COUNTDOWN_UNIT

    def __init__(self, instance, ac_key, action):
        """Initialize the Advantage Air timer control."""
        super().__init__(instance, ac_key)
        self.action = action
        self._time_key = f"countDownTo{self.action}"
        self._attr_name = f'{self._ac["name"]} Time To {self.action}'
        self._attr_unique_id = f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-timeto{self.action}'
        self._attr_state = self._ac[self._time_key]
        self._attr_icon = (
            "mdi:timer-outline"
            if self._ac[self._time_key] > 0
            else "mdi:timer-off-outline"
        )

    async def set_time_to(self, **kwargs):
        """Set the timer value."""
        value = min(720, max(0, int(kwargs[ADVANTAGE_AIR_SET_COUNTDOWN_VALUE])))
        await self.async_change({self.ac_key: {"info": {self._time_key: value}}})


class AdvantageAirZoneVent(AdvantageAirEntity, SensorEntity):
    """Representation of Advantage Air Zone Vent Sensor."""

    _attr_unit_of_measurement = PERCENTAGE

    def __init__(self):
        """Initialize an Advantage Air Zone Vent Sensor."""
        self._attr_name = f'{self._zone["name"]} Vent'
        self._attr_unique_id = f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}-vent'
        self._attr_state = (
            self._zone["value"]
            if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN
            else 0
        )
        self._attr_icon = (
            "mdi:fan"
            if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN
            else "mdi:fan-off"
        )


class AdvantageAirZoneSignal(AdvantageAirEntity, SensorEntity):
    """Representation of Advantage Air Zone wireless signal sensor."""

    _attr_unit_of_measurement = PERCENTAGE

    def __init__(self):
        """Initialize an Advantage Air Zone wireless signal sensor."""
        super().__init__()
        self._attr_name = f'{self._zone["name"]} Signal'
        self._attr_unique_id = f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}-signal'
        self._attr_icon = (
            "mdi:wifi-strength-4"
            if self._zone["rssi"] >= 80
            else "mdi:wifi-strength-3"
            if self._zone["rssi"] >= 60
            else "mdi:wifi-strength-2"
            if self._zone["rssi"] >= 40
            else "mdi:wifi-strength-1"
            if self._zone["rssi"] >= 20
            else "mdi:wifi-strength-outline"
        )
        self._attr_state = self._zone["rssi"]
