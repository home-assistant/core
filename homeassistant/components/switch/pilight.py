"""
Support for switching devices via Pilight to on and off.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.pilight/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.components.pilight as pilight
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, CONF_ID, CONF_SWITCHES, CONF_STATE,
                                 CONF_PROTOCOL)

_LOGGER = logging.getLogger(__name__)

CONF_OFF_CODE = 'off_code'
CONF_OFF_CODE_RECIEVE = 'off_code_receive'
CONF_ON_CODE = 'on_code'
CONF_ON_CODE_RECIEVE = 'on_code_receive'
CONF_SYSTEMCODE = 'systemcode'
CONF_UNIT = 'unit'
CONF_UNITCODE = 'unitcode'

DEPENDENCIES = ['pilight']

COMMAND_SCHEMA = vol.Schema({
    vol.Optional(CONF_PROTOCOL): cv.string,
    vol.Optional('on'): cv.positive_int,
    vol.Optional('off'): cv.positive_int,
    vol.Optional(CONF_UNIT): cv.positive_int,
    vol.Optional(CONF_UNITCODE): cv.positive_int,
    vol.Optional(CONF_ID): cv.positive_int,
    vol.Optional(CONF_STATE): cv.string,
    vol.Optional(CONF_SYSTEMCODE): cv.positive_int,
}, extra=vol.ALLOW_EXTRA)

SWITCHES_SCHEMA = vol.Schema({
    vol.Required(CONF_ON_CODE): COMMAND_SCHEMA,
    vol.Required(CONF_OFF_CODE): COMMAND_SCHEMA,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_OFF_CODE_RECIEVE, default=[]): vol.All(cv.ensure_list,
                                                             [COMMAND_SCHEMA]),
    vol.Optional(CONF_ON_CODE_RECIEVE, default=[]): vol.All(cv.ensure_list,
                                                            [COMMAND_SCHEMA])
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SWITCHES):
        vol.Schema({cv.string: SWITCHES_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Pilight platform."""
    switches = config.get(CONF_SWITCHES)
    devices = []

    for dev_name, properties in switches.items():
        devices.append(
            PilightSwitch(
                hass,
                properties.get(CONF_NAME, dev_name),
                properties.get(CONF_ON_CODE),
                properties.get(CONF_OFF_CODE),
                properties.get(CONF_ON_CODE_RECIEVE),
                properties.get(CONF_OFF_CODE_RECIEVE)
            )
        )

    add_devices(devices)


class PilightSwitch(SwitchDevice):
    """Representation of a Pilight switch."""

    def __init__(self, hass, name, code_on, code_off, code_on_receive,
                 code_off_receive):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._state = False
        self._code_on = code_on
        self._code_off = code_off
        self._code_on_receive = code_on_receive
        self._code_off_receive = code_off_receive

        if any(self._code_on_receive) or any(self._code_off_receive):
            hass.bus.listen(pilight.EVENT, self._handle_code)

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed, state set when correct code is received."""
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def _handle_code(self, call):
        """Check if received code by the pilight-daemon.

        If the code matches the receive on/off codes of this switch the switch
        state is changed accordingly.
        """
        # - True if off_code/on_code is contained in received code dict, not
        #   all items have to match.
        # - Call turn on/off only once, even if more than one code is received
        if any(self._code_on_receive):
            for on_code in self._code_on_receive:
                if on_code.items() <= call.data.items():
                    self.turn_on()
                    break

        if any(self._code_off_receive):
            for off_code in self._code_off_receive:
                if off_code.items() <= call.data.items():
                    self.turn_off()
                    break

    def turn_on(self):
        """Turn the switch on by calling pilight.send service with on code."""
        self._hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                 self._code_on, blocking=True)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn the switch on by calling pilight.send service with off code."""
        self._hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                 self._code_off, blocking=True)
        self._state = False
        self.schedule_update_ha_state()
