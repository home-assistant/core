from homeassistant.helpers.entity import ToggleEntity

from .const import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):

    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyAir toggle platform."""

    my = hass.data[DOMAIN][config_entry.data.get("url")]

    if "aircons" in my["coordinator"].data:
        entities = []
        for _, acx in enumerate(my["coordinator"].data["aircons"]):
            if (
                my["coordinator"].data["aircons"][acx]["info"]["freshAirStatus"]
                != "none"
            ):
                entities.append(MyAirZoneFreshAir(my, acx))
        async_add_entities(entities)
    return True


class MyAirZoneFreshAir(ToggleEntity):
    """MyAir Fresh Air Toggle"""

    def __init__(self, my, acx):
        self.coordinator = my["coordinator"]
        self.async_set_data = my["async_set_data"]
        self.device = my["device"]
        self.acx = acx

    @property
    def name(self):
        return f"{self.coordinator.data['aircons'][self.acx]['info']['name']} Fresh Air"

    @property
    def unique_id(self):
        return f"{self.coordinator.data['system']['rid']}-{self.acx}-toggle:freshair"

    @property
    def is_on(self):
        return (
            self.coordinator.data["aircons"][self.acx]["info"]["freshAirStatus"] == "on"
        )

    @property
    def should_poll(self):
        return False

    @property
    def icon(self):
        return "mdi:air-filter"

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return self.device

    async def async_turn_on(self, **kwargs):
        await self.async_set_data(
            {self.acx: {"zones": {"info": {"freshAirStatus": "on"}}}}
        )

    async def async_turn_off(self, **kwargs):
        await self.async_set_data(
            {self.acx: {"zones": {"info": {"freshAirStatus": "off"}}}}
        )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        await self.coordinator.async_request_refresh()
