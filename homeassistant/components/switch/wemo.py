"""
homeassistant.components.switch.wemo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for WeMo switches.
"""
import logging

from homeassistant.components.switch import SwitchDevice


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return WeMo switches. """
    try:
        # pylint: disable=no-name-in-module, import-error
        import homeassistant.external.pywemo.pywemo as pywemo
        import homeassistant.external.pywemo.pywemo.discovery as discovery
    except ImportError:
        logging.getLogger(__name__).exception((
            "Failed to import pywemo. "
            "Did you maybe not run `git submodule init` "
            "and `git submodule update`?"))

        return

    if discovery_info is not None:
        device = discovery.device_from_description(discovery_info)

        if device:
            add_devices_callback([WemoSwitch(device)])

        return

    logging.getLogger(__name__).info("Scanning for WeMo devices")
    switches = pywemo.discover_devices()

    # Filter out the switches and wrap in WemoSwitch object
    add_devices_callback(
        [WemoSwitch(switch) for switch in switches
         if isinstance(switch, pywemo.Switch)])


class WemoSwitch(SwitchDevice):
    """ Represents a WeMo switch within Home Assistant. """
    def __init__(self, wemo):
        self.wemo = wemo
        self.insight_params = None

    @property
    def unique_id(self):
        """ Returns the id of this WeMo switch """
        return "{}.{}".format(self.__class__, self.wemo.serialnumber)

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self.wemo.name

    @property
    def current_power_mwh(self):
        """ Current power usage in mwh. """
        if self.insight_params:
            return self.insight_params['currentpower']

    @property
    def today_power_mw(self):
        """ Today total power usage in mw. """
        if self.insight_params:
            return self.insight_params['todaymw']

    @property
    def is_on(self):
        """ True if switch is on. """
        return self.wemo.get_state()

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.wemo.on()

    def turn_off(self):
        """ Turns the switch off. """
        self.wemo.off()

    def update(self):
        """ Update WeMo state. """
        self.wemo.get_state(True)
        if self.wemo.model.startswith('Belkin Insight'):
            self.insight_params = self.wemo.insight_params
