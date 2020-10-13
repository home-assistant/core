"""Sensor platform for Advantage Air integration."""
import voluptuous as vol

from homeassistant.const import CONF_IP_ADDRESS, PERCENTAGE
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ADVANTAGE_AIR_STATE_OPEN

ADVANTAGE_AIR_SET_COUNTDOWN_VALUE = "minutes"
ADVANTAGE_AIR_SET_COUNTDOWN_UNIT = "min"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir sensor platform."""

    instance = hass.data[DOMAIN][config_entry.data[CONF_IP_ADDRESS]]

    entities = []
    for ac_index in instance["coordinator"].data["aircons"]:
        entities.append(AdvantageAirTimeTo(instance, ac_index, "On"))
        entities.append(AdvantageAirTimeTo(instance, ac_index, "Off"))
        for zone_index in instance["coordinator"].data["aircons"][ac_index]["zones"]:
            # Only show damper sensors when zone is in temperature control
            if (
                instance["coordinator"].data["aircons"][ac_index]["zones"][zone_index][
                    "type"
                ]
                != 0
            ):
                entities.append(AdvantageAirZoneVent(instance, ac_index, zone_index))
            # Only show wireless signal strength sensors when using wireless sensors
            if (
                instance["coordinator"].data["aircons"][ac_index]["zones"][zone_index][
                    "rssi"
                ]
                > 0
            ):
                entities.append(AdvantageAirZoneSignal(instance, ac_index, zone_index))
    async_add_entities(entities)

    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        "set_time_to", {vol.Required("minutes"): cv.positive_int}, "set_time_to"
    )


class AdvantageAirTimeTo(CoordinatorEntity):
    """Representation of Advantage Air timer control."""

    def __init__(self, instance, ac_index, time_period):
        """Initialize the Advantage Air timer control."""
        super().__init__(instance["coordinator"])
        self.async_change = instance["async_change"]
        self.ac_index = ac_index
        self.time_period = time_period

    @property
    def name(self):
        """Return the name."""
        return f'{self.coordinator.data["aircons"][self.ac_index]["info"]["name"]} Time To {self.time_period}'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_index}-timeto{self.time_period}'

    @property
    def state(self):
        """Return the current value."""
        return self.coordinator.data["aircons"][self.ac_index]["info"][
            f"countDownTo{self.time_period}"
        ]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ADVANTAGE_AIR_SET_COUNTDOWN_UNIT

    @property
    def icon(self):
        """Return a representative icon of the timer."""
        return ["mdi:timer-off-outline", "mdi:timer-outline"][
            self.coordinator.data["aircons"][self.ac_index]["info"][
                f"countDownTo{self.time_period}"
            ]
            > 0
        ]

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

    async def set_time_to(self, **kwargs):
        """Set the timer value."""
        if ADVANTAGE_AIR_SET_COUNTDOWN_VALUE in kwargs:
            value = min(720, max(0, int(kwargs[ADVANTAGE_AIR_SET_COUNTDOWN_VALUE])))
            await self.async_change(
                {self.ac_index: {"info": {f"countDownTo{self.time_period}": value}}}
            )


class AdvantageAirZoneVent(CoordinatorEntity):
    """Representation of Advantage Air Zone Vent Sensor."""

    def __init__(self, instance, ac_index, zone_index):
        """Initialize the Advantage Air Zone Vent Sensor."""
        super().__init__(instance["coordinator"])
        self.async_change = instance["async_change"]
        self.ac_index = ac_index
        self.zone_index = zone_index

    @property
    def name(self):
        """Return the name."""
        return f'{self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index]["name"]} Vent'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_index}-{self.zone_index}-sensor:vent'

    @property
    def state(self):
        """Return the current value of the air vent."""
        if (
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "state"
            ]
            == ADVANTAGE_AIR_STATE_OPEN
        ):
            return self.coordinator.data["aircons"][self.ac_index]["zones"][
                self.zone_index
            ]["value"]
        return 0

    @property
    def unit_of_measurement(self):
        """Return the percent sign."""
        return PERCENTAGE

    @property
    def icon(self):
        """Return a representative icon."""
        return ["mdi:fan-off", "mdi:fan"][
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "state"
            ]
            == ADVANTAGE_AIR_STATE_OPEN
        ]

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


class AdvantageAirZoneSignal(CoordinatorEntity):
    """Representation of Advantage Air Zone wireless signal sensor."""

    def __init__(self, instance, ac_index, zone_index):
        """Initialize the Advantage Air Zone wireless signal sensor."""
        super().__init__(instance["coordinator"])
        self.async_change = instance["async_change"]
        self.device = instance["device"]
        self.ac_index = ac_index
        self.zone_index = zone_index

    @property
    def name(self):
        """Return the name."""
        return f'{self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index]["name"]} Signal'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_index}-{self.zone_index}-signal'

    @property
    def state(self):
        """Return the current value of the wireless signal."""
        return self.coordinator.data["aircons"][self.ac_index]["zones"][
            self.zone_index
        ]["rssi"]

    @property
    def unit_of_measurement(self):
        """Return the percent sign."""
        return PERCENTAGE

    @property
    def icon(self):
        """Return a representative icon."""
        if (
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "rssi"
            ]
            >= 80
        ):
            return "mdi:wifi-strength-4"
        if (
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "rssi"
            ]
            >= 60
        ):
            return "mdi:wifi-strength-3"
        if (
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "rssi"
            ]
            >= 40
        ):
            return "mdi:wifi-strength-2"
        if (
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "rssi"
            ]
            >= 20
        ):
            return "mdi:wifi-strength-1"
        return "mdi:wifi-strength-outline"

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