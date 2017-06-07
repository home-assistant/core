"""
homeassistant.components.option.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo platform that has two fake options.
"""
from homeassistant.components.option import OptionDevice
from homeassistant.const import DEVICE_DEFAULT_NAME


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return demo switches. """
    add_devices_callback([
        DemoOption('Channel', ['Channel 1', 'Channel 2', 'Channel 3'], 'Channel 1', None),
        DemoOption('Level', ['Level 1', 'Level 2'], 'Level 2', 'mdi:air-conditioner')
    ])


class DemoOption(OptionDevice):
    """ Provides a demo option. """
    def __init__(self, name, options, active_option, icon):
        self._name = name or DEVICE_DEFAULT_NAME
        self._options = options
        self._active_option = active_option
        self._icon = icon

    @property
    def should_poll(self):
        """ No polling needed for a demo switch. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def icon(self):
        """ Returns the icon to use for device if any. """
        return self._icon

    @property
    def option(self):
        """ Returns the state of the entity. """
        return self._active_option

    @property
    def options(self):
        """ Returns the state of the entity. """
        return self._options

    def switch(self, option, **kwargs):
        """ Turn the entity to option 'option'. """
        self._active_option = option
        self.update_ha_state()
