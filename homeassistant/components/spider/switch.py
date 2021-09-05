"""Support for Spider switches."""
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN


async def async_setup_entry(hass, config, async_add_entities):
    """Initialize a Spider Power Plug."""
    api = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        [
            SpiderPowerPlug(api, entity)
            for entity in await hass.async_add_executor_job(api.get_power_plugs)
        ]
    )


class SpiderPowerPlug(SwitchEntity):
    """Representation of a Spider Power Plug."""

    def __init__(self, api, power_plug):
        """Initialize the Spider Power Plug."""
        self.api = api
        self.power_plug = power_plug

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.power_plug.id)},
            "name": self.power_plug.name,
            "manufacturer": self.power_plug.manufacturer,
            "model": self.power_plug.model,
        }

    @property
    def unique_id(self):
        """Return the ID of this switch."""
        return self.power_plug.id

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self.power_plug.name

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self.power_plug.is_on

    @property
    def available(self):
        """Return true if switch is available."""
        return self.power_plug.is_available

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.power_plug.turn_on()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.power_plug.turn_off()

    def update(self):
        """Get the latest data."""
        self.power_plug = self.api.get_power_plug(self.power_plug.id)
