"""
homeassistant.components.select.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo platform that has two fake select boxes.
"""
from homeassistant.components.select import SelectableDevice
from homeassistant.const import DEVICE_DEFAULT_NAME


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return demo switches. """
    add_devices_callback([
        DemoSelect('Channel', ['Channel 1', 'Channel 2', 'Channel 3'], 'Channel 1', None),
        DemoSelect('Level', ['Level 1', 'Level 2'], 'Level 2', 'mdi:air-conditioner')
    ])


class DemoSelect(SelectableDevice):
    """ Provides a demo select. """
    def __init__(self, name, options, active_option, icon):
        self._name = name or DEVICE_DEFAULT_NAME
        self._options = options
        self._active_option = active_option
        self._icon = icon

    @property
    def should_poll(self):
        """ No polling needed for a demo select. """
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
    def state(self):
        """ Returns the last selected option. """
        return self._active_option

    @property
    def options(self):
        """ Returns the available options. """
        return self._options

    def select(self, option, **kwargs):
        """ Selects the option 'option'. """
        self._active_option = option
        self.update_ha_state()
