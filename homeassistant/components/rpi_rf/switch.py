"""Support for a switch using a 433MHz module via GPIO on a Raspberry Pi."""
import importlib
import logging
from threading import RLock

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_PROTOCOL,
    CONF_SWITCHES,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_CODE_OFF = "code_off"
CONF_CODE_ON = "code_on"
CONF_GPIO = "gpio"
CONF_PULSELENGTH = "pulselength"
CONF_SIGNAL_REPETITIONS = "signal_repetitions"

DEFAULT_PROTOCOL = 1
DEFAULT_SIGNAL_REPETITIONS = 10

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CODE_OFF): vol.All(cv.ensure_list_csv, [cv.positive_int]),
        vol.Required(CONF_CODE_ON): vol.All(cv.ensure_list_csv, [cv.positive_int]),
        vol.Optional(CONF_PULSELENGTH): cv.positive_int,
        vol.Optional(
            CONF_SIGNAL_REPETITIONS, default=DEFAULT_SIGNAL_REPETITIONS
        ): cv.positive_int,
        vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): cv.positive_int,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_GPIO): cv.positive_int,
        vol.Required(CONF_SWITCHES): vol.Schema({cv.string: SWITCH_SCHEMA}),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Find and return switches controlled by a generic RF device via GPIO."""
    rpi_rf = importlib.import_module("rpi_rf")

    gpio = config.get(CONF_GPIO)
    rfdevice = rpi_rf.RFDevice(gpio)
    rfdevice_lock = RLock()
    switches = config.get(CONF_SWITCHES)

    devices = []
    for dev_name, properties in switches.items():
        devices.append(
            RPiRFSwitch(
                properties.get(CONF_NAME, dev_name),
                rfdevice,
                rfdevice_lock,
                properties.get(CONF_PROTOCOL),
                properties.get(CONF_PULSELENGTH),
                properties.get(CONF_SIGNAL_REPETITIONS),
                properties.get(CONF_CODE_ON),
                properties.get(CONF_CODE_OFF),
            )
        )
    if devices:
        rfdevice.enable_tx()

    add_entities(devices)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, lambda event: rfdevice.cleanup())


class RPiRFSwitch(SwitchEntity):
    """Representation of a GPIO RF switch."""

    def __init__(
        self,
        name,
        rfdevice,
        lock,
        protocol,
        pulselength,
        signal_repetitions,
        code_on,
        code_off,
    ):
        """Initialize the switch."""
        self._name = name
        self._state = False
        self._rfdevice = rfdevice
        self._lock = lock
        self._protocol = protocol
        self._pulselength = pulselength
        self._code_on = code_on
        self._code_off = code_off
        self._rfdevice.tx_repeat = signal_repetitions

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def _send_code(self, code_list, protocol, pulselength):
        """Send the code(s) with a specified pulselength."""
        with self._lock:
            _LOGGER.info("Sending code(s): %s", code_list)
            for code in code_list:
                self._rfdevice.tx_code(code, protocol, pulselength)
        return True

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._send_code(self._code_on, self._protocol, self._pulselength):
            self._state = True
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._send_code(self._code_off, self._protocol, self._pulselength):
            self._state = False
            self.schedule_update_ha_state()
