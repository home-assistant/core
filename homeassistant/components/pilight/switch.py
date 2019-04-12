"""Support for switching devices via Pilight to on and off."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components import pilight
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, CONF_ID, CONF_SWITCHES, CONF_STATE,
                                 CONF_PROTOCOL, STATE_ON)
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

CONF_OFF_CODE = 'off_code'
CONF_OFF_CODE_RECEIVE = 'off_code_receive'
CONF_ON_CODE = 'on_code'
CONF_ON_CODE_RECEIVE = 'on_code_receive'
CONF_SYSTEMCODE = 'systemcode'
CONF_UNIT = 'unit'
CONF_UNITCODE = 'unitcode'
CONF_ECHO = 'echo'

COMMAND_SCHEMA = vol.Schema({
    vol.Optional(CONF_PROTOCOL): cv.string,
    vol.Optional('on'): cv.positive_int,
    vol.Optional('off'): cv.positive_int,
    vol.Optional(CONF_UNIT): cv.positive_int,
    vol.Optional(CONF_UNITCODE): cv.positive_int,
    vol.Optional(CONF_ID): vol.Any(cv.positive_int, cv.string),
    vol.Optional(CONF_STATE): cv.string,
    vol.Optional(CONF_SYSTEMCODE): cv.positive_int,
}, extra=vol.ALLOW_EXTRA)

RECEIVE_SCHEMA = COMMAND_SCHEMA.extend({
    vol.Optional(CONF_ECHO): cv.boolean
})

SWITCHES_SCHEMA = vol.Schema({
    vol.Required(CONF_ON_CODE): COMMAND_SCHEMA,
    vol.Required(CONF_OFF_CODE): COMMAND_SCHEMA,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_OFF_CODE_RECEIVE, default=[]): vol.All(cv.ensure_list,
                                                             [COMMAND_SCHEMA]),
    vol.Optional(CONF_ON_CODE_RECEIVE, default=[]): vol.All(cv.ensure_list,
                                                            [COMMAND_SCHEMA])
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SWITCHES):
        vol.Schema({cv.string: SWITCHES_SCHEMA}),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
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
                properties.get(CONF_ON_CODE_RECEIVE),
                properties.get(CONF_OFF_CODE_RECEIVE)
            )
        )

    add_entities(devices)


class _ReceiveHandle:
    def __init__(self, config, echo):
        """Initialize the handle."""
        self.config_items = config.items()
        self.echo = echo

    def match(self, code):
        """Test if the received code matches the configured values.

        The received values have to be a subset of the configured options.
        """
        return self.config_items <= code.items()

    def run(self, switch, turn_on):
        """Change the state of the switch."""
        switch.set_state(turn_on=turn_on, send_code=self.echo)


class PilightSwitch(SwitchDevice, RestoreEntity):
    """Representation of a Pilight switch."""

    def __init__(self, hass, name, code_on, code_off, code_on_receive,
                 code_off_receive):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._state = False
        self._code_on = code_on
        self._code_off = code_off

        self._code_on_receive = []
        self._code_off_receive = []

        for code_list, conf in ((self._code_on_receive, code_on_receive),
                                (self._code_off_receive, code_off_receive)):
            for code in conf:
                echo = code.pop(CONF_ECHO, True)
                code_list.append(_ReceiveHandle(code, echo))

        if any(self._code_on_receive) or any(self._code_off_receive):
            hass.bus.listen(pilight.EVENT, self._handle_code)

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._state = state.state == STATE_ON

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed, state set when correct code is received."""
        return False

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return True

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
                if on_code.match(call.data):
                    on_code.run(switch=self, turn_on=True)
                    break

        if any(self._code_off_receive):
            for off_code in self._code_off_receive:
                if off_code.match(call.data):
                    off_code.run(switch=self, turn_on=False)
                    break

    def set_state(self, turn_on, send_code=True):
        """Set the state of the switch.

        This sets the state of the switch. If send_code is set to True, then
        it will call the pilight.send service to actually send the codes
        to the pilight daemon.
        """
        if send_code:
            if turn_on:
                self._hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                         self._code_on, blocking=True)
            else:
                self._hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                         self._code_off, blocking=True)

        self._state = turn_on
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs):
        """Turn the switch on by calling pilight.send service with on code."""
        self.set_state(turn_on=True)

    def turn_off(self, **kwargs):
        """Turn the switch on by calling pilight.send service with off code."""
        self.set_state(turn_on=False)
