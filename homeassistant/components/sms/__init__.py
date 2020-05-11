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

        sms = []
        start = True
        while True:
            if start:
                cursms = self._state_machine.GetNextSMS(Folder=0, Start=True)
                start = False
            else:
                cursms = self._state_machine.GetNextSMS(Folder=0, Location=cursms[0]['Location'])
            
            if not cursms:
                _LOGGER.debug("No new sms")
                break
            
            _LOGGER.debug("Fetched new sms")
            sms.append(cursms)
            self._state_machine.DeleteSMS(0, sms[0]['Location'])
        
        data = gammu.LinkSMS(sms)

        for x in data:
            v = gammu.DecodeSMS(x)

            message = x[0]

            _LOGGER.debug("Processing sms %s, decoded: %s", message, v)

            if v is None:
                text = m['Text']
            else:
                text = ""
                for e in v['Entries']:
                    if e['Buffer'] is not None:
                        text = text + e['Buffer']

            self._hass.bus.fire("{}.incoming_sms".format(DOMAIN), {
                phone: message['Number'],
                date: str(message['DateTime']),
                text
            })

        _LOGGER.info("Fetching completed")
