"""Sensor platform for Advantage Air integration."""
import voluptuous as vol

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import callback
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
            # Only show damper and temp sensors when zone is in temperature control
            if zone["type"] != 0:
                entities.append(AdvantageAirZoneVent(instance, ac_key, zone_key))
                entities.append(AdvantageAirZoneTemp(instance, ac_key, zone_key))
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
        self._time_key = f"countDownTo{action}"
        self._attr_name = f'{self._ac["name"]} Time To {action}'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-timeto{action}'
        )

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self._attr_state = self._ac[self._time_key]
        self._attr_icon = "mdi:timer-off-outline"
        if self._ac[self._time_key] > 0:
            self._attr_icon = "mdi:timer-outline"
        self.async_write_ha_state()

    async def set_time_to(self, **kwargs):
        """Set the timer value."""
        value = min(720, max(0, int(kwargs[ADVANTAGE_AIR_SET_COUNTDOWN_VALUE])))
        await self.async_change({self.ac_key: {"info": {self._time_key: value}}})


class AdvantageAirZoneVent(AdvantageAirEntity, SensorEntity):
    """Representation of Advantage Air Zone Vent Sensor."""

    _attr_unit_of_measurement = PERCENTAGE
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, instance, ac_key, zone_key):
        """Initialize an Advantage Air Zone Vent Sensor."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]} Vent'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-{zone_key}-vent'
        )

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self._attr_state = 0
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            self._attr_state = self._zone["value"]
        self._attr_icon = "mdi:fan-off"
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            self._attr_icon = "mdi:fan"
        self.async_write_ha_state()


class AdvantageAirZoneSignal(AdvantageAirEntity, SensorEntity):
    """Representation of Advantage Air Zone wireless signal sensor."""

    _attr_unit_of_measurement = PERCENTAGE
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, instance, ac_key, zone_key):
        """Initialize an Advantage Air Zone wireless signal sensor."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]} Signal'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-{zone_key}-signal'
        )

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self._attr_state = self._zone["rssi"]
        self._attr_icon = "mdi:wifi-strength-outline"
        if self._zone["rssi"] >= 80:
            self._attr_icon = "mdi:wifi-strength-4"
        elif self._zone["rssi"] >= 60:
            self._attr_icon = "mdi:wifi-strength-3"
        elif self._zone["rssi"] >= 40:
            self._attr_icon = "mdi:wifi-strength-2"
        elif self._zone["rssi"] >= 20:
            self._attr_icon = "mdi:wifi-strength-1"
        self.async_write_ha_state()


class AdvantageAirZoneTemp(AdvantageAirEntity, SensorEntity):
    """Representation of Advantage Air Zone wireless signal sensor."""

    _attr_unit_of_measurement = TEMP_CELSIUS
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_icon = "mdi:thermometer"
    _attr_entity_registry_enabled_default = False

    def __init__(self, instance, ac_key, zone_key):
        """Initialize an Advantage Air Zone Temp Sensor."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]} Temperature'
        self._attr_unique_id = f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}-temp'

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self._attr_state = self._zone["measuredTemp"]
        self.async_write_ha_state()
