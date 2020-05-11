"""The sms component."""
import logging

import gammu  # pylint: disable=import-error, no-member
import voluptuous as vol

from homeassistant.const import CONF_DEVICE
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.isdevice})},
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Configure Gateway."""
    conf = config[DOMAIN]
    device = conf.get(CONF_DEVICE)
    gateway = Gateway(hass, device)
    result = gateway.init()
    if result:
        hass.data[DOMAIN] = gateway
        return True
    else:
        return False


class Gateway:
    """Wrapper for Gammu State Machine."""

    def __init__(self, hass, device, scan_interval):
        """Initialize the Gateway object, poll as per scan interval."""
        self._state_machine = gammu.StateMachine()
        self._state_machine.SetConfig(0, dict(Device=device, Connection="at"))
        # TODO: make configurable?
        self._scan_interval = timedelta(seconds=1)
        self._hass = hass
        # TODO: do we need this?
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, lambda _: self._update())
        self._init_regular_updates(hass)

    def init(self):
        try:
            self._state_machine.Init()
        except gammu.GSMError as exc:  # pylint: disable=no-member
            _LOGGER.error("Failed to initialize, error %s", exc)
            return False
        else:
            return True

    def _init_regular_updates(self, hass):
        """Schedule regular updates at the top of the clock."""
        # TODO: what if previous update didn't end?
        track_time_interval(hass, lambda now: self._update(), self._scan_interval)

    def _update(self):
        """Get pending incoming sms and publish them to the event bus."""
        _LOGGER.debug("Fetching new sms")

        while True:
            sms = self._state_machine.GetNextSMS(0, True)
            if sms is not None:
                _LOGGER.debug("Got new sms from %s", sms)
                self._hass.bus.fire("%s.incoming_sms" % DOMAIN, sms)
                self._state_machine.DeleteSMS(0, sms[0]['Location'])
            else:
                _LOGGER.debug("No new sms")
                break
        
        _LOGGER.info("Fetching completed")
