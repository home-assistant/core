"""
Support for switch devices that can be controlled using the RaspyRFM rc module.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch/raspyrfm/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_NAME, DEVICE_DEFAULT_NAME, CONF_HOST, \
    CONF_PORT, CONF_PLATFORM, CONF_SWITCHES

REQUIREMENTS = ['raspyrfm-client==1.2.8']
_LOGGER = logging.getLogger(__name__)

CONF_GATEWAY_MANUFACTURER = 'gateway_manufacturer'
CONF_GATEWAY_MODEL = 'gateway_model'
CONF_CONTROLUNIT_MANUFACTURER = 'controlunit_manufacturer'
CONF_CONTROLUNIT_MODEL = 'controlunit_model'
CONF_CHANNEL_CONFIG = 'channel_config'
DEFAULT_HOST = '127.0.0.1'

# define configuration parameters
PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'raspyrfm',
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=None):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    vol.Optional(CONF_GATEWAY_MANUFACTURER): cv.string,
    vol.Optional(CONF_GATEWAY_MODEL): cv.string,
    vol.Required(CONF_SWITCHES, default={}): vol.Schema([{
        vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
        vol.Required(CONF_CONTROLUNIT_MANUFACTURER): cv.string,
        vol.Required(CONF_CONTROLUNIT_MODEL): cv.string,
        vol.Required(CONF_CHANNEL_CONFIG): cv.match_all,
    }])
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the RaspyRFM switch."""
    _LOGGER.info("initializing RaspyRFM Switch")

    from raspyrfm_client import RaspyRFMClient
    from raspyrfm_client.device_implementations.controlunit. \
        controlunit_constants import ControlUnitModel
    from raspyrfm_client.device_implementations.gateway.manufacturer. \
        gateway_constants import GatewayModel
    from raspyrfm_client.device_implementations.manufacturer_constants \
        import Manufacturer

    # read configuration
    gateway_manufacturer = config.get(CONF_GATEWAY_MANUFACTURER,
                                      Manufacturer.SEEGEL_SYSTEME.value)
    gateway_model = config.get(CONF_GATEWAY_MODEL, GatewayModel.RASPYRFM.value)
    host = config.get(CONF_HOST, DEFAULT_HOST)
    port = config.get(CONF_PORT)

    switches = config.get(CONF_SWITCHES)

    # create raspyrfm client
    raspyrfm_client = RaspyRFMClient()

    # try to get controlunit from client
    gateway = raspyrfm_client.get_gateway(Manufacturer(gateway_manufacturer),
                                          GatewayModel(gateway_model), host,
                                          port)

    switch_entities = []
    for switch in switches:
        name = config.get(CONF_NAME)
        controlunit_manufacturer = switch.get(CONF_CONTROLUNIT_MANUFACTURER)
        controlunit_model = switch.get(CONF_CONTROLUNIT_MODEL)
        channel_config = switch.get(CONF_CHANNEL_CONFIG)

        controlunit = raspyrfm_client.get_controlunit(
            Manufacturer(controlunit_manufacturer),
            ControlUnitModel(controlunit_model))

        # convert any key thats not a string into a string (needed for api)
        channel = {}
        for key in channel_config:
            channel[str(key)] = channel_config[key]

        # setup channel
        controlunit.set_channel_config(**channel)

        # create switch object
        switch = RaspyRFMSwitch(raspyrfm_client, name, gateway, controlunit)
        switch_entities.append(switch)

    # add it to home assistant
    add_devices(switch_entities)

    return True


class RaspyRFMSwitch(SwitchDevice):
    """Representation of a RaspyRFM switch."""

    def __init__(self, raspyrfm_client, name: str, gateway, controlunit):
        """Initialize the switch."""
        self._raspyrfm_client = raspyrfm_client

        self._name = name
        self._gateway = gateway
        self._controlunit = controlunit

        self._state = False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def should_poll(self):
        """Return True if polling should be used."""
        return False

    @property
    def assumed_state(self):
        """Return True when the current state can not be queried."""
        return True

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        from raspyrfm_client.device_implementations.controlunit.actions \
            import Action

        self._raspyrfm_client.send(self._gateway, self._controlunit, Action.ON)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        from raspyrfm_client.device_implementations.controlunit.actions \
            import Action

        if Action.OFF in self._controlunit.get_supported_actions():
            self._raspyrfm_client.send(
                self._gateway, self._controlunit, Action.OFF)
        else:
            self._raspyrfm_client.send(
                self._gateway, self._controlunit, Action.ON)

        self._state = False
        self.schedule_update_ha_state()
