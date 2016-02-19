"""
homeassistant.components.switch.mfi
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Ubiquiti mFi switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.mfi/
"""
import logging

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import validate_config

REQUIREMENTS = ['mficlient==0.2.2']

_LOGGER = logging.getLogger(__name__)

SWITCH_MODELS = [
    'Outlet',
    'Output 5v',
    'Output 12v',
    'Output 24v',
]


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up mFi sensors. """

    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['host',
                                     CONF_USERNAME,
                                     CONF_PASSWORD]},
                           _LOGGER):
        _LOGGER.error('A host, username, and password are required')
        return False

    host = config.get('host')
    port = int(config.get('port', 6443))
    username = config.get('username')
    password = config.get('password')

    from mficlient.client import MFiClient

    try:
        client = MFiClient(host, username, password, port=port)
    except client.FailedToLogin as ex:
        _LOGGER.error('Unable to connect to mFi: %s', str(ex))
        return False

    add_devices(MfiSwitch(port)
                for device in client.get_devices()
                for port in device.ports.values()
                if port.model in SWITCH_MODELS)


class MfiSwitch(SwitchDevice):
    """ An mFi switch-able device. """
    def __init__(self, port):
        self._port = port
        self._target_state = None

    @property
    def should_poll(self):
        return True

    @property
    def unique_id(self):
        return self._port.ident

    @property
    def name(self):
        return self._port.label

    @property
    def is_on(self):
        return self._port.output

    def update(self):
        self._port.refresh()
        if self._target_state is not None:
            self._port.data['output'] = float(self._target_state)
            self._target_state = None

    def turn_on(self):
        self._port.control(True)
        self._target_state = True

    def turn_off(self):
        self._port.control(False)
        self._target_state = False

    @property
    def current_power_mwh(self):
        return int(self._port.data.get('active_pwr', 0) * 1000)

    @property
    def device_state_attributes(self):
        attr = {}
        attr['volts'] = round(self._port.data.get('v_rms', 0), 1)
        attr['amps'] = round(self._port.data.get('i_rms', 0), 1)
        return attr
