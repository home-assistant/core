"""
homeassistant.components.general
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This component contains a service to shut down all devices.
"""

import homeassistant as ha
from . import chromecast, light

SERVICE_SHUTDOWN_DEVICES = "shutdown_devices"


def shutdown_devices(bus, statemachine):
    """ Tries to shutdown all devices that are currently on. """
    chromecast.turn_off(statemachine)
    light.turn_off(bus)


def setup(bus, statemachine):
    """ Setup services related to homeassistant. """

    bus.register_service(ha.DOMAIN_HOMEASSISTANT, SERVICE_SHUTDOWN_DEVICES,
                         lambda service: shutdown_devices(bus, statemachine))

    return True
