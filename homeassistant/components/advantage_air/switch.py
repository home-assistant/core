"""Switch platform for Advantage Air integration."""
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers.entity import ToggleEntity

from .const import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform setup isn't required."""
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir toggle platform."""

    instance = hass.data[DOMAIN][config_entry.data[CONF_IP_ADDRESS]]

    if "aircons" in instance["coordinator"].data:
        entities = []
        for _, ac_index in enumerate(instance["coordinator"].data["aircons"]):
            if (
                instance["coordinator"].data["aircons"][ac_index]["info"][
                    "freshAirStatus"
                ]
                != "none"
            ):
                entities.append(AdvantageAirFreshAir(instance, ac_index))
        async_add_entities(entities)
    return True


class AdvantageAirFreshAir(ToggleEntity):
    """Representation of Advantage Air fresh air control."""

    def __init__(self, instance, ac_index):
        """Initialize the Advantage Air fresh air control."""
        self.coordinator = instance["coordinator"]
        self.async_change = instance["async_change"]
        self.device = instance["device"]
        self.ac_index = ac_index
        self.aircon = self.coordinator.data["aircons"][self.ac_index]["info"]

    @property
    def name(self):
        """Return the name."""
        return f'{self.aircon["name"]} Fresh Air'

    @property
    def unique_id(self):
        """Return a unique id."""
        return (
            f'{self.coordinator.data["system"]["rid"]}-{self.ac_index}-toggle:freshair'
        )

    @property
    def is_on(self):
        """Return the fresh air status."""
        return self.aircon["freshAirStatus"] == "on"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return a representative icon of the timer."""
        return "mdi:air-filter"

    @property
    def available(self):
        """Return if platform is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return parent device information."""
        return self.device

    async def async_turn_on(self, **kwargs):
        """Turn Fresh Air On."""
        await self.async_change(
            {self.ac_index: {"zones": {"info": {"freshAirStatus": "on"}}}}
        )

    async def async_turn_off(self, **kwargs):
        """Turn Fresh Air Off."""
        await self.async_change(
            {self.ac_index: {"zones": {"info": {"freshAirStatus": "off"}}}}
        )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Request update."""
        await self.coordinator.async_request_refresh()
