"""Base class for pilight."""

import voluptuous as vol

from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    CONF_PROTOCOL,
    CONF_STATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, EVENT, SERVICE_NAME
from .const import (
    CONF_ECHO,
    CONF_OFF,
    CONF_OFF_CODE,
    CONF_OFF_CODE_RECEIVE,
    CONF_ON,
    CONF_ON_CODE,
    CONF_ON_CODE_RECEIVE,
    CONF_SYSTEMCODE,
    CONF_UNIT,
    CONF_UNITCODE,
)

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PROTOCOL): cv.string,
        vol.Optional(CONF_ON): cv.positive_int,
        vol.Optional(CONF_OFF): cv.positive_int,
        vol.Optional(CONF_UNIT): cv.positive_int,
        vol.Optional(CONF_UNITCODE): cv.positive_int,
        vol.Optional(CONF_ID): vol.Any(cv.positive_int, cv.string),
        vol.Optional(CONF_STATE): vol.Any(STATE_ON, STATE_OFF),
        vol.Optional(CONF_SYSTEMCODE): cv.positive_int,
    },
    extra=vol.ALLOW_EXTRA,
)

RECEIVE_SCHEMA = COMMAND_SCHEMA.extend({vol.Optional(CONF_ECHO): cv.boolean})

SWITCHES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ON_CODE): COMMAND_SCHEMA,
        vol.Required(CONF_OFF_CODE): COMMAND_SCHEMA,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_OFF_CODE_RECEIVE): vol.All(cv.ensure_list, [COMMAND_SCHEMA]),
        vol.Optional(CONF_ON_CODE_RECEIVE): vol.All(cv.ensure_list, [COMMAND_SCHEMA]),
    }
)


class PilightBaseDevice(RestoreEntity):
    """Base class for pilight switches and lights."""

    _attr_should_poll = False

    def __init__(self, hass, name, config):
        """Initialize a device."""
        self._hass = hass
        self._name = config.get(CONF_NAME, name)
        self._is_on = False
        self._code_on = config.get(CONF_ON_CODE)
        self._code_off = config.get(CONF_OFF_CODE)

        code_on_receive = config.get(CONF_ON_CODE_RECEIVE, [])
        code_off_receive = config.get(CONF_OFF_CODE_RECEIVE, [])

        self._code_on_receive = []
        self._code_off_receive = []

        for code_list, conf in (
            (self._code_on_receive, code_on_receive),
            (self._code_off_receive, code_off_receive),
        ):
            for code in conf:
                echo = code.pop(CONF_ECHO, True)
                code_list.append(_ReceiveHandle(code, echo))

        if any(self._code_on_receive) or any(self._code_off_receive):
            hass.bus.listen(EVENT, self._handle_code)

        self._brightness = 255

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            self._is_on = state.state == STATE_ON
            self._brightness = state.attributes.get("brightness")

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return True

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

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

    def set_state(self, turn_on, send_code=True, dimlevel=None):
        """Set the state of the switch.

        This sets the state of the switch. If send_code is set to True, then
        it will call the pilight.send service to actually send the codes
        to the pilight daemon.
        """
        if send_code:
            if turn_on:
                code = self._code_on
                if dimlevel is not None:
                    code.update({"dimlevel": dimlevel})

                self._hass.services.call(DOMAIN, SERVICE_NAME, code, blocking=True)
            else:
                self._hass.services.call(
                    DOMAIN, SERVICE_NAME, self._code_off, blocking=True
                )

        self._is_on = turn_on
        self.schedule_update_ha_state()

    def turn_on(self, **kwargs):
        """Turn the switch on by calling pilight.send service with on code."""
        self.set_state(turn_on=True)

    def turn_off(self, **kwargs):
        """Turn the switch on by calling pilight.send service with off code."""
        self.set_state(turn_on=False)


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
