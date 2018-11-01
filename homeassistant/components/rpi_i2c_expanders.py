"""
Support for controlling I²C port expanders connected to Raspberry Pi

"""
# TODO:  For more details about this component, please refer to the documentation at
# https://home-assistant.io/components/TODO/

import logging

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['smbus-cffi']  # 0.5.1

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'rpi_i2c_expanders'

g_managed_chips = None
g_pollwatcher = None


def setup(hass, config):
    """Set up RPi i²C expanders component."""
    import smbus
    from . import rpi_i2c_chips
    from . import rpi_i2c_ha_expanders
    global g_managed_chips
    # TODO: Autodetect ?
    # bus = smbus.SMBus(0)  # Rev 1 Pi uses 0
    bus = smbus.SMBus(1)  # Rev 2 Pi uses 1
    g_managed_chips = rpi_i2c_ha_expanders.ManagedChips(bus)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    _LOGGER.info("Available expander chips: %r managed by: %r",
                 g_managed_chips.supported_expanders.chip_ids(), g_managed_chips, )
    return True


def input_state_change_handler(changed_states):
    from .binary_sensor import BinarySensorDevice

    _LOGGER.debug(
        "CALLED input_state_change_handler(changed_states=%s", changed_states, )
    for changed_state in changed_states:
        _LOGGER.debug("  changed_state: %s :%s",
                      changed_state.state,  changed_state, )
        for pin, new_state in changed_state.changed_bits():
            binary_sensor = changed_state.state.expander.get_pin_dev(pin)
            _LOGGER.debug("    Updating state of %s (connected via pin: %r) to %s",
                          binary_sensor,  pin, new_state, )
            assert isinstance(binary_sensor, BinarySensorDevice)
            binary_sensor.set_state(new_state)
            binary_sensor.schedule_update_ha_state()


def start(event):
    """Stuff to do when home assistant starts."""
    import smbus
    from .rpi_i2c_chips.pollwatcher import PollWatcher
    global g_pollwatcher

    g_pollwatcher = PollWatcher(input_state_change_handler)
    for chip in g_managed_chips.chips():
        if chip.inputs_mask:
            g_pollwatcher.add_to_watch_expander(
                chip, chip.inputs_mask, log=_LOGGER)

    _LOGGER.info("Staring PollWatcher...")
    g_pollwatcher.start()


def cleanup(event):
    """Stuff to do before stopping."""
    global g_pollwatcher
    if not g_pollwatcher:
        return
    _LOGGER.info("Stopping PollWatcher %r ...", g_pollwatcher)
    g_pollwatcher.stop()
    _LOGGER.info("Waiting to join PollWatcher ...")
    g_pollwatcher.join()
    g_pollwatcher = None
    _LOGGER.info("Pollwatcher thread finished.")
