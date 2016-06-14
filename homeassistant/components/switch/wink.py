"""
Support for Wink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.wink/
"""
from homeassistant.components.wink import WinkToggleDevice

REQUIREMENTS = ['python-wink==0.7.6']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink platform."""
    import pywink

    add_devices(WinkToggleDevice(switch) for switch in pywink.get_switches())
    add_devices(WinkToggleDevice(switch) for switch in
                pywink.get_powerstrip_outlets())
    add_devices(WinkToggleDevice(switch) for switch in pywink.get_sirens())
