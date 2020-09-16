"""Sensor platform for Advantage Air integration."""
import voluptuous as vol

from homeassistant.const import (
    CONF_IP_ADDRESS,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

ADVANTAGE_AIR_SET_COUNTDOWN_VALUE = "minutes"
ADVANTAGE_AIR_SET_COUNTDOWN_UNIT = "min"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform setup isnt required."""
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir sensor platform."""

    instance = hass.data[DOMAIN][config_entry.data[CONF_IP_ADDRESS]]

    entities = []
    for _, ac_index in enumerate(instance["coordinator"].data["aircons"]):
        entities.append(AdvantageAirTimeTo(instance, ac_index, STATE_ON))
        entities.append(AdvantageAirTimeTo(instance, ac_index, STATE_OFF))
        for _, zone_index in enumerate(
            instance["coordinator"].data["aircons"][ac_index]["zones"]
        ):
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

    return True


class AdvantageAirTimeTo(Entity):
    """Representation of Advantage Air timer control."""

    def __init__(self, instance, ac_index, time_period):
        """Initialize the Advantage Air timer control."""
        self.coordinator = instance["coordinator"]
        self.async_change = instance["async_change"]
        self.device = instance["device"]
        self.ac_index = ac_index
        self.time_period = time_period

    @property
    def name(self):
        """Return the name."""
        return f"{self.coordinator.data['aircons'][self.ac_index]['info']['name']} Time To {self.time_period}"

    @property
    def unique_id(self):
        """Return a unique id."""
        return f"{self.coordinator.data['system']['rid']}-{self.ac_index}-sensor:timeto{self.time_period}"

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
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Return if platform is avaliable."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return parent device information."""
        return self.device

    async def set_time_to(self, **kwargs):
        """Set the timer value."""
        if ADVANTAGE_AIR_SET_COUNTDOWN_VALUE in kwargs:
            value = min(720, max(0, int(kwargs[ADVANTAGE_AIR_SET_COUNTDOWN_VALUE])))
            await self.async_change(
                {self.ac_index: {"info": {f"countDownTo{self.time_period}": value}}}
            )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Request update."""
        await self.coordinator.async_request_refresh()


class AdvantageAirZoneVent(Entity):
    """Representation of Advantage Air Zone Vent Sensor."""

    def __init__(self, instance, ac_index, zone_index):
        """Initialize the Advantage Air Zone Vent Sensor."""
        self.coordinator = instance["coordinator"]
        self.async_change = instance["async_change"]
        self.device = instance["device"]
        self.ac_index = ac_index
        self.zone_index = zone_index

    @property
    def name(self):
        """Return the name."""
        return f"{self.coordinator.data['aircons'][self.ac_index]['zones'][self.zone_index]['name']} Vent"

    @property
    def unique_id(self):
        """Return a unique id."""
        return f"{self.coordinator.data['system']['rid']}-{self.ac_index}-{self.zone_index}-sensor:vent"

    @property
    def state(self):
        """Return the current value of the air vent."""
        if (
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "state"
            ]
            == STATE_OPEN
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
            == STATE_OPEN
        ]

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Return if platform is avaliable."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return parent device information."""
        return self.device

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Request update."""
        await self.coordinator.async_request_refresh()


class AdvantageAirZoneSignal(Entity):
    """Representation of Advantage Air Zone wireless signal sensor."""

    def __init__(self, instance, ac_index, zone_index):
        """Initialize the Advantage Air Zone wireless signal sensor."""
        self.coordinator = instance["coordinator"]
        self.async_change = instance["async_change"]
        self.device = instance["device"]
        self.ac_index = ac_index
        self.zone_index = zone_index

    @property
    def name(self):
        """Return the name."""
        return f"{self.coordinator.data['aircons'][self.ac_index]['zones'][self.zone_index]['name']} Signal"

    @property
    def unique_id(self):
        """Return a unique id."""
        return f"{self.coordinator.data['system']['rid']}-{self.ac_index}-{self.zone_index}-sensor:signal"

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
        elif (
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "rssi"
            ]
            >= 60
        ):
            return "mdi:wifi-strength-3"
        elif (
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "rssi"
            ]
            >= 40
        ):
            return "mdi:wifi-strength-2"
        elif (
            self.coordinator.data["aircons"][self.ac_index]["zones"][self.zone_index][
                "rssi"
            ]
            >= 20
        ):
            return "mdi:wifi-strength-1"
        else:
            return "mdi:wifi-strength-outline"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Return if platform is avaliable."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return parent device information."""
        return self.device

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Request update."""
        await self.coordinator.async_request_refresh()
