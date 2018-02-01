"""
Support for controlling GPIO pins of a Raspberry Pi with gpiozero
"""
# pylint: disable=import-error
import logging

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['gpiozero==1.4.0', 'pigpio==1.38', 'RPi.GPIO==0.6.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'rpi_gpiozero'

_DEVICES = set()
_REMOTE_FACTORY = {}
_LOCAL_FACTORY = None


# pylint: disable=no-member
def setup(hass, config):
    """Set up the Raspberry PI GPIO component."""
    import os
    # Make the default pin factory 'mock' so that
    # it other pin factories can be loaded after import
    os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

    def cleanup_gpiozero(event):
        """Stuff to do before stopping."""
        for dev in _DEVICES:
            try:
                _LOGGER.info("closing device %s", dev)
                dev.close()
            except:
                _LOGGER.exception("unexpected error closing device %s", dev)
        _DEVICES.clear()

    def prepare_gpiozero(event):
        """Stuff to do when home assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpiozero)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpiozero)
    return True


def close_remote_pinfactory(hostport):
    global _REMOTE_FACTORY

    _LOGGER.info("closing pin_factory for %s", hostport)
    # Remove the pin_factory from our stored list
    pin_factory = _REMOTE_FACTORY.pop(hostport, None)
    if not pin_factory:
        return

    # Close and remove all devices associated with this pin factory
    for dev in list(_DEVICES):
        if dev.pin_factory == pin_factory:
            try:
                dev.close()
            except:
                _LOGGER.exception("error closing device")

            _DEVICES.remove(dev)

    # Close the pin_factory itself
    try:
        pin_factory.close()
    except:
        _LOGGER.exception("error closing pin factory")


def get_remote_pinfactory(hostport, timeout=1):
    global _REMOTE_FACTORY

    pin_factory = _REMOTE_FACTORY.get(hostport)

    if pin_factory:
        try:
            tick = pin_factory._connection.get_current_tick()
            _LOGGER.info("checked pin_factory for %s : %s", hostport, tick)
        except Exception as e:
            _LOGGER.error("error checking pin_factory for %s due to",
                          hostport, e)
            close_remote_pinfactory(hostport)
            pin_factory = None

    return pin_factory


def get_pinfactory(hostport=None, timeout=1):
    """
    Get the pinfactory for the configured hostport.

    :param hostport: the host/port tuple, when None local GPIO is used
    """
    global _LOCAL_FACTORY, _REMOTE_FACTORY

    # TODO do we need any thread safety here?
    pin_factory = None

    if hostport and hostport[0]:
        from gpiozero.pins.pigpio import PiGPIOFactory
        pin_factory = get_remote_pinfactory(hostport, timeout)
        # if we don't have a pin_factory, create a new one
        if pin_factory is None:
            _LOGGER.info(
                "Creating pigpiod connection to %s:%s",
                hostport[0],
                hostport[1]
            )

            try:
                pin_factory = PiGPIOFactory(
                    host=hostport[0],
                    port=hostport[1]
                )
                # We set a timeout so that we can determine if the
                # connection dies
                pin_factory._connection.sl.s.settimeout(timeout)
                _REMOTE_FACTORY[hostport] = pin_factory
            except IOError as e:
                _LOGGER.error("error connecting to pigpio due to: %s", e)
                pin_factory = None
    else:
        from gpiozero.pins.rpigpio import RPiGPIOFactory
        if _LOCAL_FACTORY is None:
            _LOCAL_FACTORY = RPiGPIOFactory()
        pin_factory = _LOCAL_FACTORY
    return pin_factory


def setup_button(port, pull_mode, bouncetime, hostport):
    """
    Set up a GPIO as input (a.k.a Button in Gpiozero.

    :param port: the GPIO port using BCM numbering.
    :param pull_mode: 'UP' or 'DOWN' to pull the GPIO pin high or low.
    :param bouncetime: the software bounce compensation in msec.
    :param hostport: the remote host/port, None for local.
    """
    from gpiozero import Button

    if pull_mode.upper() not in ('UP', 'DOWN'):
        raise ValueError("invalid pull_mode %s", pull_mode)

    if bouncetime < 0:
        raise ValueError("invalid bouncetime %s", bouncetime)

    pin_factory = get_pinfactory(hostport)
    if pin_factory is None:
        return None

    btn = Button(
        port,
        pull_up=(pull_mode.upper() == 'UP'),
        bounce_time=float(bouncetime) / 1e3,
        pin_factory=pin_factory
    )

    # add the button to the _DEVICES list so we can cleanup on shutdown
    _DEVICES.add(btn)

    return btn
