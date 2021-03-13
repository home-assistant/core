"""Support for switches that can be controlled using the RaspyRFM rc module."""
from raspyrfm_client import RaspyRFMClient
from raspyrfm_client.device_implementations.controlunit.actions import Action
from raspyrfm_client.device_implementations.controlunit.controlunit_constants import (
    ControlUnitModel,
)
from raspyrfm_client.device_implementations.gateway.manufacturer.gateway_constants import (
    GatewayModel,
)
from raspyrfm_client.device_implementations.manufacturer_constants import Manufacturer
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SWITCHES,
    DEVICE_DEFAULT_NAME,
)
import homeassistant.helpers.config_validation as cv

CONF_GATEWAY_MANUFACTURER = "gateway_manufacturer"
CONF_GATEWAY_MODEL = "gateway_model"
CONF_CONTROLUNIT_MANUFACTURER = "controlunit_manufacturer"
CONF_CONTROLUNIT_MODEL = "controlunit_model"
CONF_CHANNEL_CONFIG = "channel_config"
DEFAULT_HOST = "127.0.0.1"

# define configuration parameters
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_GATEWAY_MANUFACTURER): cv.string,
        vol.Optional(CONF_GATEWAY_MODEL): cv.string,
        vol.Required(CONF_SWITCHES): vol.Schema(
            [
                {
                    vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
                    vol.Required(CONF_CONTROLUNIT_MANUFACTURER): cv.string,
                    vol.Required(CONF_CONTROLUNIT_MODEL): cv.string,
                    vol.Required(CONF_CHANNEL_CONFIG): {cv.string: cv.match_all},
                }
            ]
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RaspyRFM switch."""

    gateway_manufacturer = config.get(
        CONF_GATEWAY_MANUFACTURER, Manufacturer.SEEGEL_SYSTEME.value
    )
    gateway_model = config.get(CONF_GATEWAY_MODEL, GatewayModel.RASPYRFM.value)
    host = config[CONF_HOST]
    port = config.get(CONF_PORT)
    switches = config[CONF_SWITCHES]

    raspyrfm_client = RaspyRFMClient()
    gateway = raspyrfm_client.get_gateway(
        Manufacturer(gateway_manufacturer), GatewayModel(gateway_model), host, port
    )
    switch_entities = []
    for switch in switches:
        name = switch[CONF_NAME]
        controlunit_manufacturer = switch[CONF_CONTROLUNIT_MANUFACTURER]
        controlunit_model = switch[CONF_CONTROLUNIT_MODEL]
        channel_config = switch[CONF_CHANNEL_CONFIG]

        controlunit = raspyrfm_client.get_controlunit(
            Manufacturer(controlunit_manufacturer), ControlUnitModel(controlunit_model)
        )

        controlunit.set_channel_config(**channel_config)

        switch = RaspyRFMSwitch(raspyrfm_client, name, gateway, controlunit)
        switch_entities.append(switch)

    add_entities(switch_entities)


class RaspyRFMSwitch(SwitchEntity):
    """Representation of a RaspyRFM switch."""

    def __init__(self, raspyrfm_client, name: str, gateway, controlunit):
        """Initialize the switch."""
        self._raspyrfm_client = raspyrfm_client

        self._name = name
        self._gateway = gateway
        self._controlunit = controlunit

        self._state = None

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

        self._raspyrfm_client.send(self._gateway, self._controlunit, Action.ON)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""

        if Action.OFF in self._controlunit.get_supported_actions():
            self._raspyrfm_client.send(self._gateway, self._controlunit, Action.OFF)
        else:
            self._raspyrfm_client.send(self._gateway, self._controlunit, Action.ON)

        self._state = False
        self.schedule_update_ha_state()
