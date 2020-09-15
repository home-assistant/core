import voluptuous as vol

from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.helpers.entity import Entity

from .const import ADVANTAGE_AIR_SET_COUNTDOWN_VALUE, DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyAir sensor platform."""

    my = hass.data[DOMAIN][config_entry.data.get("url")]

    entities = []
    for _, acx in enumerate(my["coordinator"].data["aircons"]):
        entities.append(MyAirTimeTo(my, acx, "On"))
        entities.append(MyAirTimeTo(my, acx, "Off"))
        for _, zx in enumerate(my["coordinator"].data["aircons"][acx]["zones"]):
            # Only show damper sensors when zone is in temperature control
            if my["coordinator"].data["aircons"][acx]["zones"][zx]["type"] != 0:
                entities.append(MyAirZoneVent(my, acx, zx))
            # Only show wireless signal strength sensors when using wireless sensors
            if my["coordinator"].data["aircons"][acx]["zones"][zx]["rssi"] > 0:
                entities.append(MyAirZoneSignal(my, acx, zx))
    async_add_entities(entities)

    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        "set_time_to", {vol.Required("minutes"): cv.positive_int}, "set_time_to"
    )

    return True


class MyAirTimeTo(Entity):
    """MyAir CountDown"""

    def __init__(self, my, acx, to):
        self.coordinator = my["coordinator"]
        self.async_set_data = my["async_set_data"]
        self.device = my["device"]
        self.acx = acx
        self.to = to

    @property
    def name(self):
        return f"{self.coordinator.data['aircons'][self.acx]['info']['name']} Time To {self.to}"

    @property
    def unique_id(self):
        return f"{self.coordinator.data['system']['rid']}-{self.acx}-sensor:timeto{self.to}"

    @property
    def state(self):
        return self.coordinator.data["aircons"][self.acx]["info"][
            f"countDownTo{self.to}"
        ]

    @property
    def unit_of_measurement(self):
        return "min"

    @property
    def icon(self):
        return ["mdi:timer-off-outline", "mdi:timer-outline"][
            self.coordinator.data["aircons"][self.acx]["info"][f"countDownTo{self.to}"]
            > 0
        ]

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return self.device

    async def set_time_to(self, **kwargs):
        if ADVANTAGE_AIR_SET_COUNTDOWN_VALUE in kwargs:
            value = min(720, max(0, int(kwargs[ADVANTAGE_AIR_SET_COUNTDOWN_VALUE])))
            await self.async_set_data(
                {self.acx: {"info": {f"countDownTo{self.to}": value}}}
            )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        await self.coordinator.async_request_refresh()


class MyAirZoneVent(Entity):
    """MyAir Zone Vent"""

    def __init__(self, my, acx, zx):
        self.coordinator = my["coordinator"]
        self.async_set_data = my["async_set_data"]
        self.device = my["device"]
        self.acx = acx
        self.zx = zx

    @property
    def name(self):
        return f"{self.coordinator.data['aircons'][self.acx]['zones'][self.zx]['name']} Vent"

    @property
    def unique_id(self):
        return (
            f"{self.coordinator.data['system']['rid']}-{self.acx}-{self.zx}-sensor:vent"
        )

    @property
    def state(self):
        if (
            self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["state"]
            == ADVANTAGE_AIR_ZONE_OPEN
        ):
            return self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["value"]
        else:
            return 0

    @property
    def unit_of_measurement(self):
        return "%"

    @property
    def icon(self):
        return ["mdi:fan-off", "mdi:fan"][
            self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["state"]
            == ADVANTAGE_AIR_ZONE_OPEN
        ]

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return self.device

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        await self.coordinator.async_request_refresh()


class MyAirZoneSignal(Entity):
    """MyAir Zone Signal"""

    def __init__(self, my, acx, zx):
        self.coordinator = my["coordinator"]
        self.async_set_data = my["async_set_data"]
        self.device = my["device"]
        self.acx = acx
        self.zx = zx

    @property
    def name(self):
        return f"{self.coordinator.data['aircons'][self.acx]['zones'][self.zx]['name']} Signal"

    @property
    def unique_id(self):
        return f"{self.coordinator.data['system']['rid']}-{self.acx}-{self.zx}-sensor:signal"

    @property
    def state(self):
        return self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["rssi"]

    @property
    def unit_of_measurement(self):
        return "%"

    @property
    def icon(self):
        if self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["rssi"] >= 80:
            return "mdi:wifi-strength-4"
        elif self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["rssi"] >= 60:
            return "mdi:wifi-strength-3"
        elif self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["rssi"] >= 40:
            return "mdi:wifi-strength-2"
        elif self.coordinator.data["aircons"][self.acx]["zones"][self.zx]["rssi"] >= 20:
            return "mdi:wifi-strength-1"
        else:
            return "mdi:wifi-strength-outline"

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return self.device

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        await self.coordinator.async_request_refresh()
