"""Support for Spider switches."""
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN


async def async_setup_entry(hass, config, async_add_entities):
    """Initialize a Spider thermostat."""
    api = hass.data[DOMAIN][config.entry_id]

    entities = [SpiderPowerPlug(api, entity) for entity in api.get_power_plugs()]

    async_add_entities(entities)


class SpiderPowerPlug(SwitchEntity):
    """Representation of a Spider Power Plug."""

    def __init__(self, api, power_plug):
        """Initialize the Vera device."""
        self.api = api
        self.power_plug = power_plug

    @property
    def unique_id(self):
        """Return the ID of this switch."""
        return self.power_plug.id

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self.power_plug.name

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return round(self.power_plug.current_energy_consumption)

    @property
    def today_energy_kwh(self):
        """Return the current power usage in Kwh."""
        return round(self.power_plug.today_energy_consumption / 1000, 2)

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
        self.power_plug = self.api.get_power_plug(self.unique_id)
