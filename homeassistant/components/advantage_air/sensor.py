"""Sensor platform for Advantage Air integration."""
import voluptuous as vol

from homeassistant.const import PERCENTAGE
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ADVANTAGE_AIR_STATE_OPEN, DOMAIN

ADVANTAGE_AIR_SET_COUNTDOWN_VALUE = "minutes"
ADVANTAGE_AIR_SET_COUNTDOWN_UNIT = "min"
ADVANTAGE_AIR_SERVICE_SET_TIME_TO = "set_time_to"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir sensor platform."""

    instance = hass.data[DOMAIN][config_entry.entry_id]

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

    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {vol.Required("minutes"): cv.positive_int},
        "set_time_to",
    )


class AdvantageAirSensor(CoordinatorEntity):
    """Parent class for Sensor entities."""

    def __init__(self, instance, ac_key, zone_key=None):
        """Initialize common aspects of an Advantage Air sensor."""
        super().__init__(instance["coordinator"])
        self.async_change = instance["async_change"]
        self.ac_key = ac_key
        self.zone_key = zone_key

    @property
    def _ac(self):
        return self.coordinator.data["aircons"][self.ac_key]["info"]

    @property
    def _zone(self):
        if self.zone_key:
            return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key]
        return None

    @property
    def device_info(self):
        """Return parent device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.data["system"]["rid"])},
            "name": self.coordinator.data["system"]["name"],
            "manufacturer": "Advantage Air",
            "model": self.coordinator.data["system"]["sysType"],
            "sw_version": self.coordinator.data["system"]["myAppRev"],
        }


class AdvantageAirTimeTo(AdvantageAirSensor):
    """Representation of Advantage Air timer control."""

    def __init__(self, instance, ac_key, time_period):
        """Initialize the Advantage Air timer control."""
        super().__init__(instance, ac_key)
        self.time_period = time_period

    @property
    def name(self):
        """Return the name."""
        return f'{self._ac["name"]} Time To {self.time_period}'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-timeto{self.time_period}'

    @property
    def state(self):
        """Return the current value."""
        return self._ac[f"countDownTo{self.time_period}"]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ADVANTAGE_AIR_SET_COUNTDOWN_UNIT

    @property
    def icon(self):
        """Return a representative icon of the timer."""
        if self._ac[f"countDownTo{self.time_period}"] > 0:
            return "mdi:timer-outline"
        return "mdi:timer-off-outline"

    async def set_time_to(self, **kwargs):
        """Set the timer value."""
        value = min(720, max(0, int(kwargs[ADVANTAGE_AIR_SET_COUNTDOWN_VALUE])))
        await self.async_change(
            {self.ac_key: {"info": {f"countDownTo{self.time_period}": value}}}
        )


class AdvantageAirZoneVent(AdvantageAirSensor):
    """Representation of Advantage Air Zone Vent Sensor."""

    @property
    def name(self):
        """Return the name."""
        return f'{self._zone["name"]} Vent'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}-vent'

    @property
    def state(self):
        """Return the current value of the air vent."""
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            return self._zone["value"]
        return 0

    @property
    def unit_of_measurement(self):
        """Return the percent sign."""
        return PERCENTAGE

    @property
    def icon(self):
        """Return a representative icon."""
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            return "mdi:fan"
        return "mdi:fan-off"


class AdvantageAirZoneSignal(AdvantageAirSensor):
    """Representation of Advantage Air Zone wireless signal sensor."""

    @property
    def name(self):
        """Return the name."""
        return f'{self._zone["name"]} Signal'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}-signal'

    @property
    def state(self):
        """Return the current value of the wireless signal."""
        return self._zone["rssi"]

    @property
    def unit_of_measurement(self):
        """Return the percent sign."""
        return PERCENTAGE

    @property
    def icon(self):
        """Return a representative icon."""
        if self._zone["rssi"] >= 80:
            return "mdi:wifi-strength-4"
        if self._zone["rssi"] >= 60:
            return "mdi:wifi-strength-3"
        if self._zone["rssi"] >= 40:
            return "mdi:wifi-strength-2"
        if self._zone["rssi"] >= 20:
            return "mdi:wifi-strength-1"
        return "mdi:wifi-strength-outline"
