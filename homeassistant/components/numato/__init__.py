"""
Support for controlling GPIO pins of a Numato Labs USB GPIO expander.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/numato
"""
# pylint: disable=import-error
import logging

import numato_gpio as gpio

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP

_LOGGER = logging.getLogger(__name__)

DOMAIN = "numato"


# pylint: disable=no-member


def setup(hass, config):
    """Initialize the integration by discovering available Numato devices."""
    gpio.discover()
    _LOGGER.info(
        "Initializing Numato 32 port USB GPIO expanders with IDs: %s",
        ", ".join(str(d) for d in gpio.devices),
    )

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        _LOGGER.debug("Clean up Numato GPIO")
        gpio.cleanup()
        PORTS_IN_USE.clear()

    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
        _LOGGER.debug("Setup cleanup at stop for Numato GPIO")
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)

    return True


PORTS_IN_USE = dict()


def check_port_free(device_id, port, direction):
    """Check whether a port is still free set up.

    Fail with exception if it has already been registered.
    """
    if (device_id, port) not in PORTS_IN_USE:
        PORTS_IN_USE[(device_id, port)] = direction
    else:
        raise gpio.NumatoGpioError(
            "Device {} Port {} already in use as {}.".format(
                device_id,
                port,
                "input" if PORTS_IN_USE[(device_id, port)] == gpio.IN else "output",
            )
        )


def check_device_id(device_id):
    """Check whether a device has been discovered.

    Fail with exception.
    """
    if device_id not in gpio.devices:
        raise gpio.NumatoGpioError(f"Device {device_id} not available.")


def setup_output(device_id, port):
    """Set up a GPIO as output."""
    check_device_id(device_id)
    check_port_free(device_id, port, gpio.OUT)
    gpio.devices[device_id].setup(port, gpio.OUT)


def setup_input(device_id, port):
    """Set up a GPIO as input."""
    check_device_id(device_id)
    gpio.devices[device_id].setup(port, gpio.IN)
    check_port_free(device_id, port, gpio.IN)


def write_output(device_id, port, value):
    """Write a value to a GPIO."""
    gpio.devices[device_id].write(port, value)


def read_input(device_id, port):
    """Read a value from a GPIO."""
    return gpio.devices[device_id].read(port)


def read_adc_input(device_id, port):
    """Read an ADC value from a GPIO ADC port."""
    return gpio.devices[device_id].adc_read(port)


def edge_detect(device_id, port, event_callback):
    """Add detection for RISING and FALLING events."""
    gpio.devices[device_id].add_event_detect(port, event_callback, gpio.BOTH)
    gpio.devices[device_id].notify(True)
