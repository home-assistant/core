"""Binary Sensor platform for Advantage Air integration."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.const import CONF_IP_ADDRESS

from .const import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform setup isnt required."""
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir motion platform."""

    instance = hass.data[DOMAIN][config_entry.data[CONF_IP_ADDRESS]]

    if "aircons" in instance["coordinator"].data:
        entities = []
        for _, ac_index in enumerate(instance["coordinator"].data["aircons"]):
            entities.append(AdvantageAirZoneFilter(instance, ac_index))
            for _, zone_index in enumerate(
                instance["coordinator"].data["aircons"][ac_index]["zones"]
            ):
                # Only add motion sensor when motion is enabled
                if (
                    instance["coordinator"].data["aircons"][ac_index]["zones"][
                        zone_index
                    ]["motionConfig"]
                    == 0
                ):
                    entities.append(
                        AdvantageAirZoneMotion(instance, ac_index, zone_index)
                    )
        async_add_entities(entities)
    return True


class AdvantageAirZoneFilter(BinarySensorEntity):
    """AdvantageAir Filter."""

    def __init__(self, instance, ac_index):
        """Initialize the Advantage Air Zone Filter."""
        self.coordinator = instance["coordinator"]
        self.async_change = instance["async_change"]
        self.device = instance["device"]
        self.ac_index = ac_index

    @property
    def name(self):
        """Return the name."""
        return (
            f"{self.coordinator.data['aircons'][self.ac_index]['info']['name']} Filter"
        )

    @property
    def unique_id(self):
        """Return a unique id."""
        return f"{self.coordinator.data['system']['rid']}-{self.ac_index}-binary:filter"

    @property
    def device_class(self):
        """Return the device class of the vent."""
        return DEVICE_CLASS_PROBLEM

    @property
    def is_on(self):
        """Return if filter needs cleaning."""
        return self.coordinator.data["aircons"][self.ac_index]["info"][
            "filterCleanStatus"
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


class AdvantageAirZoneMotion(BinarySensorEntity):
    """AdvantageAir Zone Motion."""

    def __init__(self, instance, ac_index, zone_index):
        """Initialize the Advantage Air Zone Motion sensor."""
        self.coordinator = instance["coordinator"]
        self.async_change = instance["async_change"]
        self.device = instance["device"]
        self.ac_index = ac_index
        self.zone_index = zone_index

    @property
    def name(self):
        """Return the name."""
        return f"{self.coordinator.data['aircons'][self.ac_index]['zones'][self.zone_index]['name']} Motion"

    @property
    def unique_id(self):
        """Return a unique id."""
        return f"{self.coordinator.data['system']['rid']}-{self.ac_index}-{self.zone_index}-binary:motion"

    @property
    def device_class(self):
        """Return the device class of the vent."""
        return DEVICE_CLASS_MOTION

    @property
    def is_on(self):
        """Return if motion is detect."""
        return self.coordinator.data["aircons"][self.ac_index]["zones"][
            self.zone_index
        ]["motion"]

    @property
    def device_state_attributes(self):
        """Return additional motion configuration."""
        return {
            "motionConfig": self.coordinator.data["aircons"][self.ac_index]["zones"][
                self.zone_index
            ]["motionConfig"]
        }

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
