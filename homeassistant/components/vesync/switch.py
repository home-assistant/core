"""Support for Etekcity VeSync switches."""
import logging
from homeassistant.components.switch import (SwitchDevice)

from .common import DOMAIN, CONF_SWITCHES, async_add_entities_retry

_LOGGER = logging.getLogger(__name__)

ENERGY_UPDATE_INT = 21600


"""def setup_platform(hass, config, add_entities, discovery_info=None):

    if discovery_info is None:
        return

    switches = []

    manager = hass.data[DOMAIN]['manager']

    if manager.outlets is not None and manager.outlets:
        if len(manager.outlets) == 1:
            count_string = 'switch'
        else:
            count_string = 'switches'

        _LOGGER.info("Discovered %d VeSync %s",
                     len(manager.outlets), count_string)

        for switch in manager.outlets:
            switch._energy_update_interval = ENERGY_UPDATE_INT
            switches.append(VeSyncSwitchHA(switch))
            _LOGGER.info("Added a VeSync switch named '%s'",
                         switch.device_name)
    else:
        _LOGGER.info("No VeSync switches or outlets found")

    add_entities(switches)
"""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches"""
    await async_add_entities_retry(
        hass,
        async_add_entities,
        hass.data[DOMAIN][CONF_SWITCHES],
        add_entity
    )
    return True


def add_entity(device, async_add_entities):
    """Check if device is online and add entity"""
    device.update()

    async_add_entities([VeSyncSwitchHA(device)], update_before_add=True)


class VeSyncSwitchHA(SwitchDevice):
    """Representation of a VeSync switch."""

    def __init__(self, plug):
        """Initialize the VeSync switch device."""
        self.smartplug = plug

    @property
    def unique_id(self):
        """Return the ID of this switch."""
        return self.smartplug.cid

    @property
    def name(self):
        """Return the name of the switch."""
        return self.smartplug.device_name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr['active_time'] = self.smartplug.active_time
        attr['voltage'] = self.smartplug.voltage
        attr['active_time'] = self.smartplug.active_time
        attr['weekly_energy_total'] = self.smartplug.weekly_energy_total
        attr['monthly_energy_total'] = self.smartplug.monthly_energy_total
        attr['yearly_energy_total'] = self.smartplug.yearly_energy_total
        return attr

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.smartplug.power

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return self.smartplug.energy_today

    @property
    def available(self) -> bool:
        """Return True if switch is available."""
        return self.smartplug.connection_status == "online"

    @property
    def is_on(self):
        """Return True if switch is on."""
        return self.smartplug.device_status == "on"

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.smartplug.turn_on()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.smartplug.turn_off()

    def update(self):
        """Handle data changes for node values."""
        self.smartplug.update()
        self.smartplug.update_energy()
