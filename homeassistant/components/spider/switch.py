"""Support for Spider switches."""
import logging

from homeassistant.components.switch import SwitchDevice

from . import DOMAIN as SPIDER_DOMAIN

DEPENDENCIES = ['spider']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Spider thermostat."""
    if discovery_info is None:
        return

    devices = [SpiderPowerPlug(hass.data[SPIDER_DOMAIN]['controller'], device)
               for device in hass.data[SPIDER_DOMAIN]['power_plugs']]

    add_entities(devices, True)


class SpiderPowerPlug(SwitchDevice):
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
