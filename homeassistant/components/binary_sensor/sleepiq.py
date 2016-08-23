"""
Support for SleepIQ sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sleepiq/
"""
from homeassistant.components import sleepiq

DEPENDENCIES = ['sleepiq']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the SleepIQ sensors."""
    if discovery_info is None:
        return
